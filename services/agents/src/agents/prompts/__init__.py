"""Prompt files, versioned by folder: ``prompts/<agent>/<version>/{system.md, user.md.j2}`` (F12-FR-05)."""

from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, StrictUndefined

ROOT = Path(__file__).parent


@dataclass(frozen=True)
class Prompt:
    agent: str
    version: str
    system: str
    _user: str

    def render_user(self, **variables: object) -> str:
        """The user message; a missing variable is an error, not an empty string."""
        template = Environment(undefined=StrictUndefined, keep_trailing_newline=False).from_string(self._user)
        return template.render(**variables)


def load_prompt(agent: str, version: str) -> Prompt:
    folder = ROOT / agent / version
    return Prompt(
        agent=agent,
        version=version,
        system=(folder / "system.md").read_text().strip(),
        _user=(folder / "user.md.j2").read_text().strip(),
    )
