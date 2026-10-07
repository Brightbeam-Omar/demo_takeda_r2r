"""Scenario steps (F13-FR-01): the YAML schema, the loader and the template filler.

A step is a title, a one-line talk track, preconditions (state checks against what the app shows) and an
ordered list of actions. Identifiers that the generator picks (a sample id, a lot number, a deviation number)
are named in ``vars`` and looked up when the step runs, so the YAML never holds a number a reseed changes.
"""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

ACTION_KINDS = ("event", "clock_advance", "run_pipeline", "wait_sync", "run_agent")
SERVICES = ("erp", "lims", "qms", "app")
PRECONDITION_KINDS = ("stage", "air_gap", "open_deviations", "adjusted_need_by", "proposals")
DEFAULT_USER = (
    "admin"  # OQ-150: there is no `system` app user, so actions run as admin unless a step says otherwise
)
# The wheel carries the scenarios next to the package; a source checkout keeps them beside `src`.
_HERE = Path(__file__).resolve().parent
DEFAULT_PATH = next(
    (
        p
        for p in (_HERE / "scenarios" / "site_a.yaml", _HERE.parents[1] / "scenarios" / "site_a.yaml")
        if p.exists()
    ),
    _HERE / "scenarios" / "site_a.yaml",
)

_TEMPLATE = re.compile(r"\$\{([a-z_][a-z0-9_.]*)\}")


class StepError(ValueError):
    """The YAML is not a valid scenario."""


@dataclass(frozen=True)
class Precondition:
    kind: str
    batch: str
    equals: str | bool | int
    message: str


@dataclass(frozen=True)
class Action:
    kind: str
    label: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Step:
    id: str
    title: str
    talk_track: str
    preconditions: tuple[Precondition, ...]
    actions: tuple[Action, ...]
    vars: dict[str, dict[str, Any]] = field(default_factory=dict)


def _precondition(step_id: str, raw: dict[str, Any]) -> Precondition:
    kind = raw.get("kind")
    if kind not in PRECONDITION_KINDS:
        raise StepError(f"{step_id}: unknown precondition kind {kind!r}")
    for key in ("batch", "equals", "message"):
        if key not in raw:
            raise StepError(f"{step_id}: a {kind} precondition needs {key!r}")
    return Precondition(kind, raw["batch"], raw["equals"], raw["message"])


def _action(step_id: str, raw: dict[str, Any]) -> Action:
    params = dict(raw)
    kind = params.pop("do", None)
    if kind not in ACTION_KINDS:
        raise StepError(f"{step_id}: unknown action {kind!r} (one of {', '.join(ACTION_KINDS)})")
    label = str(params.pop("label", kind.replace("_", " ")))
    if kind == "event":
        if params.get("service") not in SERVICES:
            raise StepError(f"{step_id}: an event needs service: one of {', '.join(SERVICES)}")
        if "path" not in params:
            raise StepError(f"{step_id}: an event needs a path")
    if kind == "clock_advance" and not (("days" in params) ^ ("hours" in params)):
        raise StepError(f"{step_id}: clock_advance needs exactly one of days or hours")
    return Action(kind, label, params)


def parse_steps(document: dict[str, Any]) -> list[Step]:
    steps: list[Step] = []
    for raw in document.get("steps", []):
        step_id = raw.get("id")
        if not step_id:
            raise StepError("every step needs an id")
        if any(step.id == step_id for step in steps):
            raise StepError(f"duplicate step id {step_id}")
        for key in ("title", "talk_track", "actions"):
            if not raw.get(key):
                raise StepError(f"{step_id}: missing {key}")
        steps.append(
            Step(
                id=step_id,
                title=raw["title"],
                talk_track=raw["talk_track"],
                preconditions=tuple(_precondition(step_id, p) for p in raw.get("preconditions", [])),
                actions=tuple(_action(step_id, a) for a in raw["actions"]),
                vars=dict(raw.get("vars", {})),
            )
        )
    return steps


def load_steps(path: Path | None = None) -> list[Step]:
    source = path or Path(os.environ.get("SCENARIO_FILE", str(DEFAULT_PATH)))
    return parse_steps(yaml.safe_load(source.read_text(encoding="utf-8")))


def fill(value: Any, variables: dict[str, Any]) -> Any:
    """Replace ``${name}`` and ``${name.field}`` in every string of a nested value (unknown names raise)."""
    if isinstance(value, str):

        def lookup(match: re.Match[str]) -> str:
            current: Any = variables
            for part in match.group(1).split("."):
                if not isinstance(current, dict) or part not in current:
                    raise StepError(f"unknown variable ${{{match.group(1)}}}")
                current = current[part]
            return str(current)

        return _TEMPLATE.sub(lookup, value)
    if isinstance(value, list):
        return [fill(item, variables) for item in value]
    if isinstance(value, dict):
        return {key: fill(item, variables) for key, item in value.items()}
    return value
