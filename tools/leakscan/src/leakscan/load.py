"""Load and compile the denylist [F02-FR-02, F02-FR-03].

Source priority: env ``LEAKSCAN_DENYLIST`` (the list itself, newline-separated), then the gitignored
file ``.leakscan/denylist.txt``. The first source that holds at least one rule wins; they are not merged.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

ENV_VAR = "LEAKSCAN_DENYLIST"
DENYLIST_FILE = Path(".leakscan") / "denylist.txt"


class UsageError(Exception):
    """A configuration or usage problem. The CLI exits 2."""


@dataclass(frozen=True)
class Rule:
    number: int  # 1-based, among non-blank, non-comment entries
    source: str  # the entry as written
    pattern: re.Pattern[str]


@dataclass(frozen=True)
class Denylist:
    rules: tuple[Rule, ...]
    origin: str  # "env" or "file"


def _compile(entry: str, number: int) -> re.Pattern[str]:
    if entry.startswith("re:"):
        expression = entry[3:]
    else:
        expression = f"(?<![A-Za-z0-9]){re.escape(entry)}(?![A-Za-z0-9])"
    try:
        return re.compile(expression, re.IGNORECASE)
    except re.error as error:
        raise UsageError(f"denylist rule #{number} is not a valid regular expression: {error}") from error


def parse_denylist(text: str) -> tuple[Rule, ...]:
    rules: list[Rule] = []
    for raw in text.splitlines():
        entry = raw.strip()
        if not entry or entry.startswith("#"):
            continue
        number = len(rules) + 1
        rules.append(Rule(number, entry, _compile(entry, number)))
    return tuple(rules)


def load_denylist(env: Mapping[str, str], root: Path) -> Denylist | None:
    """Return the active denylist, or ``None`` when none is configured."""
    value = env.get(ENV_VAR, "")
    if value.strip():
        stripped = value.strip()
        if "\n" not in stripped and Path(stripped).is_file():
            raise UsageError(
                f"{ENV_VAR} must hold the denylist content, not a path ('{stripped}'). "
                f"Locally, put the terms in {DENYLIST_FILE.as_posix()} and leave the variable unset."
            )
        rules = parse_denylist(value)
        if rules:
            return Denylist(rules, "env")
    path = root / DENYLIST_FILE
    if path.is_file():
        rules = parse_denylist(path.read_text(encoding="utf-8", errors="replace"))
        if rules:
            return Denylist(rules, "file")
    return None


def is_ci(env: Mapping[str, str]) -> bool:
    return env.get("CI", "").strip().lower() in {"true", "1"}


def no_denylist_outcome(env: Mapping[str, str]) -> tuple[int, str]:
    """Exit code and message when no denylist is configured: fail in CI, warn locally."""
    if is_ci(env):
        return 1, (
            f"error: no denylist found and CI is set. Set the {ENV_VAR} secret "
            f"(newline-separated terms) for this job."
        )
    return 0, (
        f"warning: no denylist found, nothing was scanned. Set {ENV_VAR} or create "
        f"{DENYLIST_FILE.as_posix()} (see {DENYLIST_FILE.parent.as_posix()}/denylist.example.txt)."
    )
