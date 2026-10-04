"""Scan commit messages and author names in a revision range [F02 OQ-014]."""

import subprocess
from collections.abc import Sequence
from pathlib import Path

from leakscan.load import Rule, UsageError
from leakscan.scan import Finding, scan_text, scan_value

_FIELD = "\x1f"
_RECORD = "\x1e"


def scan_commits(rev_range: str, cwd: Path, rules: Sequence[Rule]) -> tuple[list[Finding], int]:
    """Return findings and the number of commits scanned.

    Findings use the virtual path ``commits/<full sha>`` (also the allow-list path). The location is
    ``author`` for the author name and email, or the 1-based line of the message.
    """
    result = subprocess.run(
        ["git", "log", f"--format=%H{_FIELD}%an{_FIELD}%ae{_FIELD}%B{_RECORD}", rev_range],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise UsageError(f"git log {rev_range} failed: {result.stderr.strip()}")
    findings: list[Finding] = []
    scanned = 0
    for record in result.stdout.split(_RECORD):
        if not record.strip():
            continue
        sha, name, email, message = record.strip("\n").split(_FIELD, 3)
        scanned += 1
        path = f"commits/{sha}"
        hits = scan_value(f"{name} <{email}>", rules, "author") + scan_text(message, rules)
        findings.extend(Finding(path, h.location, h.matched, h.rule) for h in hits)
    return findings, scanned
