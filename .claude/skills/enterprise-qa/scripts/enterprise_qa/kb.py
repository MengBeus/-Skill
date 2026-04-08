from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path


_CJK_OR_WORD = re.compile(r"[\u4e00-\u9fff]+|[A-Za-z0-9][A-Za-z0-9.+_-]*")
_DATE_PATTERN = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


def tokenize(text: str) -> set[str]:
    tokens: set[str] = set()
    for match in _CJK_OR_WORD.findall(text.lower()):
        tokens.add(match)
        if re.fullmatch(r"[\u4e00-\u9fff]+", match):
            for size in (2, 3):
                if len(match) < size:
                    continue
                for index in range(0, len(match) - size + 1):
                    tokens.add(match[index : index + size])
    return {token for token in tokens if token.strip()}


@dataclass(slots=True)
class Section:
    file_path: Path
    file_name: str
    heading: str
    text: str
    tokens: set[str]
    title_tokens: set[str]
    file_date: date | None

    @property
    def source_label(self) -> str:
        if self.heading:
            return f"{self.file_name} §{self.heading}"
        return self.file_name


class KnowledgeBase:
    def __init__(self, root_path: Path) -> None:
        self.root_path = root_path
        self.sections = self._load_sections()

    def _load_sections(self) -> list[Section]:
        sections: list[Section] = []
        for path in sorted(self.root_path.rglob("*.md")):
            sections.extend(self._parse_file(path))
        return sections

    def _parse_file(self, path: Path) -> list[Section]:
        relative_name = path.relative_to(self.root_path).as_posix()
        lines = path.read_text(encoding="utf-8").splitlines()
        stack: list[str] = []
        chunk: list[str] = []
        sections: list[Section] = []

        def flush() -> None:
            text = "\n".join(chunk).strip()
            if not text:
                return
            heading = " > ".join(stack[1:]) if len(stack) > 1 else (stack[0] if stack else "")
            sections.append(
                Section(
                    file_path=path,
                    file_name=relative_name,
                    heading=heading,
                    text=text,
                    tokens=tokenize(text),
                    title_tokens=tokenize(f"{relative_name} {heading}"),
                    file_date=_parse_file_date(relative_name),
                )
            )

        for line in lines:
            stripped = line.strip()
            heading_match = re.match(r"^(#{1,6})\s+(.*)$", stripped)
            if heading_match:
                flush()
                chunk = []
                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()
                while len(stack) >= level:
                    stack.pop()
                stack.append(title)
                continue
            chunk.append(line)

        flush()
        return sections

    def search(
        self,
        query: str,
        preferred_files: tuple[str, ...] = (),
        limit: int = 3,
    ) -> list[Section]:
        query_tokens = tokenize(query)
        ranked: list[tuple[int, Section]] = []

        for section in self.sections:
            score = 0
            if preferred_files and any(name in section.file_name for name in preferred_files):
                score += 5
            score += 3 * len(query_tokens & section.title_tokens)
            score += len(query_tokens & section.tokens)
            if query in section.text:
                score += 4
            if score > 0:
                ranked.append((score, section))

        ranked.sort(
            key=lambda item: (
                -item[0],
                item[1].file_date is None,
                item[1].file_date or date.min,
                item[1].file_name,
            )
        )
        return [section for _, section in ranked[:limit]]

    def find_best(self, query: str, preferred_files: tuple[str, ...] = ()) -> Section | None:
        results = self.search(query, preferred_files=preferred_files, limit=1)
        return results[0] if results else None


def _parse_file_date(file_name: str) -> date | None:
    match = _DATE_PATTERN.search(file_name)
    if not match:
        return None
    return date.fromisoformat(match.group(0))


def extract_matching_lines(section: Section, keywords: list[str], limit: int = 3) -> list[str]:
    selected: list[str] = []
    for raw_line in section.text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("---"):
            continue
        if line.startswith("|") and set(line) <= {"|", "-", " "}:
            continue
        if any(keyword in line for keyword in keywords):
            selected.append(line.lstrip("- ").strip())
        if len(selected) >= limit:
            break
    return selected


def extract_table_row(section: Section, keyword: str) -> list[str] | None:
    for raw_line in section.text.splitlines():
        line = raw_line.strip()
        if not line.startswith("|") or keyword not in line:
            continue
        parts = [part.strip() for part in line.strip("|").split("|")]
        if len(parts) >= 2:
            return parts
    return None
