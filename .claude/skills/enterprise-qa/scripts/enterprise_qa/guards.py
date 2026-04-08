from __future__ import annotations

import re


_SQL_PATTERNS = [
    re.compile(r"(?i)\bselect\b.+\bfrom\b"),
    re.compile(r"(?i)\bunion\b.+\bselect\b"),
    re.compile(r"(?i)\b(drop|delete|truncate|insert|update)\b"),
    re.compile(r"--"),
    re.compile(r"/\*"),
    re.compile(r";"),
    re.compile(r"'1'\s*=\s*'1'"),
]


def is_potential_sql_injection(question: str) -> bool:
    text = question.strip()
    return any(pattern.search(text) for pattern in _SQL_PATTERNS)
