from __future__ import annotations

import sqlite3
import sys

from enterprise_qa.config import AppConfig
from enterprise_qa.db import ensure_database


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    try:
        config = AppConfig.load()
        config.validate_runtime()
        created = ensure_database(config.db_path)
    except (FileNotFoundError, OSError, sqlite3.Error, ValueError) as exc:
        print(f"Enterprise QA data preparation failed: {exc}", file=sys.stderr)
        return 1

    if created:
        print(f"Created database: {config.db_path}")
    else:
        print(f"Database already exists: {config.db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
