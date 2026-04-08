from __future__ import annotations

import argparse
import sys
import trace
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = SKILL_ROOT / "scripts"
PACKAGE_ROOT = SCRIPTS_ROOT / "enterprise_qa"


def _run_tests() -> unittest.result.TestResult:
    if str(SCRIPTS_ROOT) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_ROOT))
    suite = unittest.defaultTestLoader.discover(str(SKILL_ROOT / "tests"))
    return unittest.TextTestRunner(verbosity=2).run(suite)


def _collect_coverage(counts: dict[tuple[str, int], int]) -> tuple[list[tuple[str, int, int, float]], float]:
    rows: list[tuple[str, int, int, float]] = []
    covered_total = 0
    executable_total = 0

    for path in sorted(PACKAGE_ROOT.glob("*.py")):
        if path.name == "__init__.py":
            continue
        executable = {line for line in trace._find_executable_linenos(str(path)) if line > 0}
        covered = {
            lineno
            for (filename, lineno), count in counts.items()
            if Path(filename).resolve() == path.resolve() and count > 0
        }
        covered_total += len(covered)
        executable_total += len(executable)
        percent = (len(covered) / len(executable) * 100.0) if executable else 100.0
        rows.append((path.name, len(covered), len(executable), percent))

    overall = (covered_total / executable_total * 100.0) if executable_total else 100.0
    return rows, overall


def main() -> int:
    parser = argparse.ArgumentParser(description="Run enterprise QA tests with stdlib trace coverage.")
    parser.add_argument("--min", type=float, default=80.0, help="Minimum aggregate coverage percentage")
    args = parser.parse_args()

    tracer = trace.Trace(count=True, trace=False, ignoredirs=[sys.prefix, sys.exec_prefix])
    result = tracer.runfunc(_run_tests)
    if not result.wasSuccessful():
        return 1

    rows, overall = _collect_coverage(tracer.results().counts)
    print("\nCoverage summary for scripts/enterprise_qa:")
    for name, covered, executable, percent in rows:
        print(f"  {name}: {covered}/{executable} lines ({percent:.2f}%)")
    print(f"  overall: {overall:.2f}%")

    if overall < args.min:
        print(f"Coverage check failed: expected at least {args.min:.2f}%", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
