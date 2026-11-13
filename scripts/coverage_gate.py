"""Fail when a core package's line coverage is below its floor (docs/testing.md, plan C2).

    python3 scripts/coverage_gate.py coverage.json janus/cascades=90 janus/resolution=90 ...

Reads the JSON report of coverage.py (`pytest --cov --cov-report=json`). A package is every file
under the given path prefix. Standard library only.
"""

from __future__ import annotations

import json
import sys


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        sys.stderr.write("usage: coverage_gate.py coverage.json PREFIX=FLOOR ...\n")
        return 2
    files = json.loads(open(argv[0], encoding="utf-8").read())["files"]
    failed = False
    for spec in argv[1:]:
        prefix, floor = spec.rsplit("=", 1)
        covered = total = 0
        for path, data in files.items():
            if path.startswith(prefix.rstrip("/") + "/"):
                covered += data["summary"]["covered_lines"]
                total += data["summary"]["num_statements"]
        if total == 0:
            print(f"FAIL {prefix}: no measured file")
            failed = True
            continue
        pct = 100 * covered / total
        ok = pct >= float(floor)
        failed |= not ok
        print(f"{'ok  ' if ok else 'FAIL'} {prefix}: {pct:.1f}% of {total} lines (floor {floor}%)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
