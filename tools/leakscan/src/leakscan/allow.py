"""Hashed allow-list for false positives [F02-FR-08].

``.leakscan/allow.txt`` is committed, so entries must not reveal terms. Each line is
``<repo-relative posix path>:<sha256 hex of the lowercased matched text>``. Paths are literal (no globs).
Blank lines and lines starting with ``#`` are ignored. To make an entry::

    printf %s 'the matched text' | tr 'A-Z' 'a-z' | shasum -a 256
"""

import hashlib
import re
from collections.abc import Iterable
from pathlib import Path

from leakscan.load import UsageError
from leakscan.scan import Finding

ALLOW_FILE = Path(".leakscan") / "allow.txt"
_HEX64 = re.compile(r"[0-9a-f]{64}")

AllowList = frozenset[tuple[str, str]]


def allow_hash(matched: str) -> str:
    return hashlib.sha256(matched.lower().encode("utf-8")).hexdigest()


def parse_allowlist(text: str) -> AllowList:
    entries: set[tuple[str, str]] = set()
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        path, _, digest = line.rpartition(":")
        if not path or not _HEX64.fullmatch(digest):
            raise UsageError(f"allow-list line {number} must be '<path>:<sha256 hex, lowercase>'")
        entries.add((path, digest))
    return frozenset(entries)


def load_allowlist(root: Path) -> AllowList:
    path = root / ALLOW_FILE
    if not path.is_file():
        return frozenset()
    return parse_allowlist(path.read_text(encoding="utf-8", errors="replace"))


def apply_allowlist(findings: Iterable[Finding], allow: AllowList) -> list[Finding]:
    return [f for f in findings if (f.path, allow_hash(f.matched)) not in allow]
