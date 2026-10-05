"""The Overview query: filters, period, exceptions-first order, flow strip and alerts (F09-FR-02, FR-03).

Semantics (OQ-059): values inside one filter are ORed and the filters are ANDed. Periods are Monday to Sunday
weeks and calendar months in the site timezone, taken from the demo clock; only the window's end matters
(``r2r_core.sla.in_period``), so overdue rows roll into every current window.
"""

import calendar
import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel
from r2r_core.profile import SiteProfile
from r2r_core.sla import in_period

from app_api.schemas import Freshness, RowOut
from app_api.services.compose import ComposedRow

PERIODS = ("all", "this_week", "last_week", "next_week", "this_month", "custom")
FLAG_NAMES = (
    "on_hold", "erp_blocked", "re_eval", "offsite", "full_spec", "expedite", "ud_rejected", "lims_rejected",
    "air_gap", "late",
)  # fmt: skip
TOP_AIR_GAPS = 5


class InvalidFilter(ValueError):
    """A filter value the API cannot use (answered as 422)."""


@dataclass(frozen=True)
class Filters:
    types: Sequence[str] = ()
    classes: Sequence[str] = ()
    campaigns: Sequence[str] = ()
    stage: str | None = None
    flags: Sequence[str] = ()
    period: str = "all"
    date_from: dt.date | None = None
    date_to: dt.date | None = None
    q: str | None = None
    extra: dict[str, str] = field(default_factory=dict)


def window(filters: Filters, today: dt.date) -> tuple[dt.date, dt.date] | None:
    period = filters.period
    monday = today - dt.timedelta(days=today.weekday())
    if period == "all":
        return None
    if period == "this_week":
        return monday, monday + dt.timedelta(days=6)
    if period == "last_week":
        return monday - dt.timedelta(days=7), monday - dt.timedelta(days=1)
    if period == "next_week":
        return monday + dt.timedelta(days=7), monday + dt.timedelta(days=13)
    if period == "this_month":
        return today.replace(day=1), today.replace(day=calendar.monthrange(today.year, today.month)[1])
    if period == "custom":
        if filters.date_from is None or filters.date_to is None:
            raise InvalidFilter("period=custom needs both from and to")
        return filters.date_from, filters.date_to
    raise InvalidFilter(f"period must be one of {', '.join(PERIODS)}")


def has_flag(row: ComposedRow, name: str) -> bool:
    if name == "expedite":
        return row.expedite
    if name == "air_gap":
        return row.air_gap
    if name == "late":
        return row.plan.late
    return bool(row.facts[name])


def _matches(row: ComposedRow, filters: Filters, period: tuple[dt.date, dt.date] | None, stage: bool) -> bool:
    facts = row.facts
    if filters.types and facts["molecule_type"] not in filters.types:
        return False
    if filters.classes and facts["material_class"] not in filters.classes:
        return False
    if filters.campaigns and facts["campaign"] not in filters.campaigns:
        return False
    if stage and filters.stage and facts["stage_key"] != filters.stage:
        return False
    if filters.flags and not any(has_flag(row, name) for name in filters.flags):
        return False
    if filters.q:
        needle = filters.q.lower()
        haystack = (facts["material_no"], facts["material_desc"] or "", facts["batch_no"])
        if not any(needle in value.lower() for value in haystack):
            return False
    return in_period(row.plan, row.stage_terminal, period)


def select(
    rows: Sequence[ComposedRow], filters: Filters, today: dt.date, *, with_stage: bool = True
) -> list[ComposedRow]:
    """The rows that pass the filters, in exceptions-first order (without the stage filter if asked)."""
    period = window(filters, today)
    kept = [row for row in rows if _matches(row, filters, period, with_stage)]
    return sorted(kept, key=lambda row: row.sort_key)


class FlowEntry(BaseModel):
    stage_key: str
    label: str
    count: int
    breached: bool
    late_count: int


class AlertOut(BaseModel):
    kind: Literal["air_gap", "late", "on_hold", "rejected"]
    count: int
    rows: list[RowOut] = []
    detail: dict[str, int] = {}


class OverviewOut(BaseModel):
    freshness: Freshness
    flow_strip: list[FlowEntry]
    on_hold_count: int
    total: int
    mode: Literal["snapshot", "due_in_period"]
    alerts: list[AlertOut]
    rows: list[RowOut]


def build_overview(
    rows: Sequence[ComposedRow], filters: Filters, profile: SiteProfile, today: dt.date, fresh: Freshness
) -> OverviewOut:
    labels = {stage.key: stage.label for stage in profile.stages}
    shown = select(rows, filters, today)
    unstaged = select(rows, filters, today, with_stage=False)
    flow = [
        FlowEntry(
            stage_key=stage.key,
            label=stage.label,
            count=sum(1 for row in unstaged if row.facts["stage_key"] == stage.key),
            breached=any(row.plan.late for row in unstaged if row.facts["stage_key"] == stage.key),
            late_count=sum(1 for row in unstaged if row.facts["stage_key"] == stage.key and row.plan.late),
        )
        for stage in profile.stages
    ]
    gaps = sorted((row for row in unstaged if row.air_gap), key=lambda row: (-row.air_gap_hours, row.row_key))
    ud_rejected = sum(1 for row in unstaged if row.facts["ud_rejected"])
    lims_rejected = sum(1 for row in unstaged if row.facts["lims_rejected"])
    on_hold = sum(1 for row in unstaged if row.facts["on_hold"])
    alerts = [
        AlertOut(kind="air_gap", count=len(gaps), rows=[RowOut.of(r, labels) for r in gaps[:TOP_AIR_GAPS]]),
        AlertOut(kind="late", count=sum(1 for row in unstaged if row.plan.late)),
        AlertOut(kind="on_hold", count=on_hold),
        AlertOut(
            kind="rejected",
            count=sum(1 for row in unstaged if row.facts["ud_rejected"] or row.facts["lims_rejected"]),
            detail={"ud_rejected": ud_rejected, "lims_rejected": lims_rejected},
        ),
    ]
    return OverviewOut(
        freshness=fresh,
        flow_strip=flow,
        on_hold_count=on_hold,
        total=len(shown),
        mode="snapshot" if filters.period == "all" else "due_in_period",
        alerts=alerts,
        rows=[RowOut.of(row, labels) for row in shown],
    )
