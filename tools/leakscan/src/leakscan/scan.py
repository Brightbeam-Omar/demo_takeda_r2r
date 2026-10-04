"""Match denylist rules against text and format findings [F02-FR-03, F02-FR-05]."""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from leakscan.load import Rule


@dataclass(frozen=True)
class Hit:
    """A match inside one unit of text. ``location`` is a line number, a cell reference, or similar."""

    location: str
    matched: str
    rule: int


@dataclass(frozen=True)
class Finding:
    path: str  # repo-relative posix path (or a virtual path such as commits/<sha>)
    location: str
    matched: str
    rule: int

    def render(self) -> str:
        return f"{self.path}:{self.location}: {mask(self.matched)} (rule #{self.rule})"


def mask(matched: str) -> str:
    """First character plus ``***``, so logs never carry the term."""
    return f"{matched[:1]}***"


def scan_value(text: str, rules: Sequence[Rule], location: str) -> list[Hit]:
    """Scan one value (a cell, a path, a name) and report every match at ``location``."""
    hits: list[Hit] = []
    for rule in rules:
        for match in rule.pattern.finditer(text):
            if match.group():
                hits.append(Hit(location, match.group(), rule.number))
    return hits


def scan_text(text: str, rules: Sequence[Rule]) -> list[Hit]:
    """Scan multi-line text; locations are 1-based line numbers."""
    hits: list[Hit] = []
    for number, line in enumerate(text.splitlines(), start=1):
        hits.extend(scan_value(line, rules, str(number)))
    return hits


def scan_file(path: Path, display: str, rules: Sequence[Rule]) -> list[Finding]:
    """Scan a text file. (Reader dispatch for other formats is added in T3.)"""
    text = path.read_bytes().decode("utf-8", errors="replace")
    return [Finding(display, hit.location, hit.matched, hit.rule) for hit in scan_text(text, rules)]
