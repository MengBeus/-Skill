from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any


_ENV_PATTERN = re.compile(r"\$\{([^}:]+)(?::-([^}]+))?\}")


def _expand_env(raw: str) -> str:
    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        default = match.group(2) or ""
        return os.environ.get(name, default)

    return _ENV_PATTERN.sub(replace, raw)


def _parse_scalar(raw: str) -> Any:
    value = raw.strip().strip('"').strip("'")
    value = _expand_env(value)
    if value.isdigit():
        return int(value)
    return value


def parse_simple_yaml(path: Path) -> dict[str, Any]:
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip():
            continue
        stripped = raw_line.lstrip()
        if stripped.startswith("#"):
            continue
        indent = len(raw_line) - len(stripped)
        key, sep, value = stripped.partition(":")
        if not sep:
            continue

        while stack and indent <= stack[-1][0]:
            stack.pop()

        current = stack[-1][1]
        key = key.strip()
        value = value.strip()
        if not value:
            new_map: dict[str, Any] = {}
            current[key] = new_map
            stack.append((indent, new_map))
            continue
        current[key] = _parse_scalar(value)

    return root


@dataclass(slots=True)
class AppConfig:
    skill_root: Path
    repo_root: Path
    db_path: Path
    knowledge_root: Path
    timezone: str
    reference_date: date

    @classmethod
    def load(cls) -> "AppConfig":
        return cls.load_from()

    @classmethod
    def load_from(
        cls,
        config_path: Path | None = None,
        *,
        skill_root: Path | None = None,
    ) -> "AppConfig":
        skill_root = skill_root or Path(__file__).resolve().parents[2]
        repo_root = skill_root.parents[2]
        config_path = config_path or (skill_root / "config.yaml")
        parsed = parse_simple_yaml(config_path) if config_path.exists() else {}

        db_value = os.environ.get("ENTERPRISE_QA_DB_PATH") or parsed.get("database", {}).get(
            "path",
            str(repo_root / "enterprise-qa-data" / "enterprise.db"),
        )
        kb_value = os.environ.get("ENTERPRISE_QA_KB_PATH") or parsed.get(
            "knowledge_base", {}
        ).get("root_path", str(repo_root / "enterprise-qa-data" / "knowledge"))

        timezone = str(parsed.get("timezone", "Asia/Shanghai"))
        reference_raw = str(parsed.get("reference_date", "2026-03-27"))

        def resolve_path(raw: str) -> Path:
            path = Path(_expand_env(raw))
            if path.is_absolute():
                return path
            return (config_path.parent / path).resolve()

        return cls(
            skill_root=skill_root,
            repo_root=repo_root,
            db_path=resolve_path(str(db_value)),
            knowledge_root=resolve_path(str(kb_value)),
            timezone=timezone,
            reference_date=date.fromisoformat(reference_raw),
        )

    def validate_runtime(self) -> None:
        if self.knowledge_root.exists():
            if not self.knowledge_root.is_dir():
                raise FileNotFoundError(f"Knowledge base path is not a directory: {self.knowledge_root}")
        else:
            raise FileNotFoundError(f"Knowledge base directory was not found: {self.knowledge_root}")

        if self.db_path.exists():
            if not self.db_path.is_file():
                raise FileNotFoundError(f"Database path is not a file: {self.db_path}")
            return

        schema_path = self.db_path.parent / "schema.sql"
        seed_path = self.db_path.parent / "seed_data.sql"
        if not schema_path.exists() or not seed_path.exists():
            raise FileNotFoundError(
                "Database file is missing and schema.sql/seed_data.sql were not found beside it: "
                f"{self.db_path.parent}"
            )
