"""Looking things up for a step: the row a batch shows in the app, and the identifiers the sources assigned.

Preconditions read the application API, so a check matches what the presenter sees on screen (OQ-150).
Variables read the source simulators, which hold the numbers the generator picked.
"""

from typing import Any

from scenario.gateway import CallFailed, Gateway
from scenario.steps import Precondition, StepError


def app_row(gateway: Gateway, batch: str) -> dict[str, Any]:
    """The Overview row of a story batch (the one with the lowest lot type if it has several lots)."""
    answer = gateway.call("app", "GET", "/api/overview", params={"q": batch}, user="admin")
    mine: list[dict[str, Any]] = [row for row in answer["rows"] if row["batch_no"] == batch]
    if not mine:
        raise CallFailed(f"the app shows no row for batch {batch} (has the data been synced?)")
    return sorted(mine, key=lambda row: row["lot_type"])[0]


def check_precondition(gateway: Gateway, precondition: Precondition) -> str | None:
    """None when the check holds; otherwise the message to show."""
    kind, batch = precondition.kind, precondition.batch
    if kind == "proposals":
        proposals = gateway.call("agents", "GET", "/proposals", user="admin")
        actual: Any = len(proposals)
    else:
        row = app_row(gateway, batch)
        if kind == "stage":
            actual = row["stage_key"]
        elif kind == "air_gap":
            actual = bool(row["air_gap"])
        elif kind == "adjusted_need_by":
            actual = row["adjusted_need_by_date"] is not None
        else:  # open_deviations
            actual = deviation_count(gateway, batch)
    return None if actual == precondition.equals else precondition.message


def deviation_count(gateway: Gateway, batch: str) -> int:
    return len(open_deviations(gateway, batch))


def open_deviations(gateway: Gateway, batch: str) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = gateway.get("qms", "/deviations", batch_no=batch)
    return [deviation for deviation in found if deviation.get("closed_on") is None]


def resolve_var(gateway: Gateway, name: str, spec: dict[str, Any]) -> Any:
    """One ``vars`` entry of a step: ``{resolve: row|sample|deviation, batch: B1042}``."""
    kind, batch = spec.get("resolve"), spec.get("batch", "")
    if kind == "row":
        return app_row(gateway, batch)
    if kind == "sample":  # the sample LIMS has not approved or rejected yet
        samples = gateway.get("lims", "/samples", batch_no=batch)
        open_samples = [s for s in samples if s["status"] in ("registered", "in_progress")]
        if not open_samples:
            raise StepError(f"{name}: LIMS has no open sample for {batch}")
        return open_samples[-1]
    if kind == "deviation":  # the open deviation linked to the batch
        found = open_deviations(gateway, batch)
        if not found:
            raise StepError(f"{name}: QMS has no open deviation for {batch}")
        return found[0]
    raise StepError(f"{name}: unknown resolver {kind!r}")
