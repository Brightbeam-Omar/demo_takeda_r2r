"""``python -m doctor [--expect-up]``: print each check and the fix of a failing one; exit 1 on a failure."""

import argparse
import os
import sys
from pathlib import Path

from doctor.checks import run_all
from doctor.system import System

MARK = {"ok": "ok  ", "fail": "FAIL", "skip": "skip"}


def read_env(root: Path) -> dict[str, str]:
    """The process environment over the values in ``.env`` (the same variables compose reads)."""
    values: dict[str, str] = {}
    try:
        lines = (root / ".env").read_text().splitlines()
    except OSError:
        lines = []
    for line in lines:
        if "=" in line and not line.lstrip().startswith("#"):
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip().strip("'\"")
    return {**values, **os.environ}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="doctor", description=__doc__)
    parser.add_argument("--expect-up", action="store_true", help="fail when the stack is not running")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[4]
    results = run_all(System(root, read_env(root)), expect_up=args.expect_up)
    for result in results:
        print(f"[{MARK[result.status]}] {result.name}: {result.detail}")
        if result.status == "fail":
            print(f"        fix: {result.fix}")
    failed = [r for r in results if r.status == "fail"]
    if failed:
        print(f"\ndoctor: {len(failed)} of {len(results)} checks failed. Fix them, then run `make doctor`.")
        return 1
    print(f"\ndoctor: all {len(results)} checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
