"""Command line entry point: ``python -m leakscan [paths…] [--commits RANGE]``.

Exit codes: 0 clean, 1 findings (or no denylist in CI), 2 usage or configuration error.
"""

import argparse
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from leakscan.allow import apply_allowlist, load_allowlist
from leakscan.commits import scan_commits
from leakscan.discover import default_files, display_path, explicit_files, git_root
from leakscan.load import UsageError, load_denylist, no_denylist_outcome
from leakscan.scan import SkippedFile, scan_file, scan_path

LARGE_FILE_BYTES = 200 * 1024 * 1024


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m leakscan",
        description="Scan for client-identifying terms. Denylist: env LEAKSCAN_DENYLIST (content), "
        "else .leakscan/denylist.txt.",
    )
    parser.add_argument("paths", nargs="*", help="files or directories to scan (default: the git file set)")
    parser.add_argument("--commits", metavar="REV_RANGE", help="scan commit messages and authors in a range")
    return parser


def _say(message: str, *, err: bool = False) -> None:
    print(message, file=sys.stderr if err else sys.stdout)


def run(argv: Sequence[str], env: Mapping[str, str], cwd: Path) -> int:
    args = _parser().parse_args(list(argv))
    root = git_root(cwd) or cwd
    denylist = load_denylist(env, root)
    if denylist is None:
        code, message = no_denylist_outcome(env)
        _say(message, err=True)
        return code
    rules = denylist.rules
    allow = load_allowlist(root)

    skipped: dict[str, list[str]] = {"binary": [], "unreadable": []}
    if args.commits:
        findings, scanned = scan_commits(args.commits, cwd, rules)
        unit = f"{scanned} commit(s)"
    else:
        files = explicit_files(args.paths, cwd, root) if args.paths else default_files(root)
        findings = []
        for file in files:
            display = display_path(file, root)
            if file.stat().st_size > LARGE_FILE_BYTES:
                _say(f"warning: {display} is over 200 MB; scanning may be slow", err=True)
            findings.extend(scan_path(display, rules))
            try:
                findings.extend(scan_file(file, display, rules))
            except SkippedFile as reason:
                skipped["binary" if str(reason) == "binary" else "unreadable"].append(display)
        unit = f"{len(files)} file(s)"

    findings = apply_allowlist(findings, allow)
    for finding in findings:
        _say(finding.render())
    for kind, names in skipped.items():
        if names:
            _say(f"leakscan: skipped {len(names)} {kind} files (not scanned): " + ", ".join(names))
    if findings:
        _say(f"leakscan: {len(findings)} finding(s) in {unit}, denylist from {denylist.origin}", err=True)
        return 1
    _say(f"leakscan: clean, {unit} scanned, denylist from {denylist.origin}")
    return 0


def main(
    argv: Sequence[str] | None = None,
    env: Mapping[str, str] | None = None,
    cwd: Path | None = None,
) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    environment = os.environ if env is None else env
    try:
        return run(arguments, environment, cwd or Path.cwd())
    except UsageError as error:
        _say(f"error: {error}", err=True)
        return 2
