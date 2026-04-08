from __future__ import annotations

import argparse
import sqlite3
import sys

from enterprise_qa.engine import EnterpriseQA


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Answer enterprise QA exam questions.")
    parser.add_argument("question", help="Natural-language enterprise question")
    args = parser.parse_args()

    try:
        engine = EnterpriseQA()
    except (FileNotFoundError, OSError, sqlite3.Error, ValueError) as exc:
        print(f"Enterprise QA skill failed to initialize: {exc}", file=sys.stderr)
        return 1

    try:
        print(engine.answer(args.question))
        return 0
    finally:
        engine.close()


if __name__ == "__main__":
    raise SystemExit(main())
