"""The Overview query: filters, period, exceptions-first order, flow strip and alerts (F09-FR-02, FR-03).

Semantics (OQ-059): values inside one filter are ORed and the filters are ANDed. Periods are Monday to Sunday
weeks and calendar months in the site timezone, taken from the demo clock; only the window's end matters
(``r2r_core.sla.in_period``), so overdue rows roll into every current window.
"""

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel
from r2r_core.applies_if import parse_applies_if
from r2r_core.profile import SiteProfile, Stage
from r2r_core.sla import in_period, month_window

from app_api.schemas import Freshness, RowOut
from app_api.services.compose import ComposedRow
from app_api.services.windows import adjusted_rows, air_gap_rows

PERIODS = ("all", "this_week", "last_week", "next_week", "this_month", "last_month", "next_month", "custom")
FLAG_NAMES = (
    "on_hold", "erp_blocked", "re_eval", "offsite", "full_spec", "expedite", "ud_rejected", "lims_rejected",
    "air_gap", "late", "released", "release_on_coa",
)  # fmt: skip
TOP_AIR_GAPS = 5
UNKNOWN_CLASS = "unknown"  # reserved key: rows whose material class is NULL (OQ-086)
MONTH_OFFSETS = {"last_month": -1, "this_month": 0, "next_month": 1}


class InvalidFilter(ValueError):
    """A filter value the API cannot use (answered as 422)."""


@dataclass(frozen=True)
class Filters:
    types: Sequence[str] = ()
    classes: Sequence[str] = ()
    campaigns: Sequence[str] = ()
    stages: Sequence[str] = ()  # repeated `stage=`: ORed (F17-FR-05)
    include_released: bool = False  # F17-FR-10
    flags: Sequence[str] = ()
    period: str = "all"
    date_from: dt.date | None = None
    date_to: dt.date | None = None
    q: str | None = None
    bookmarked_keys: frozenset[str] | None = None  # the user's bookmarks when `bookmarked` is on (F16-FR-04)
    extra: dict[str, str] = field(default_factory=dict)

    @property
    def wants_released(self) -> bool:
        """Released lots show only when asked for: the flag, the Released card or the parameter."""
        return self.include_released or "released" in self.stages or "released" in self.flags


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
    if period in MONTH_OFFSETS:
        return month_window(today, MONTH_OFFSETS[period])
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
    if name == "released":
        return row.stage_terminal
    if name == "release_on_coa":
        return row.coa_release is not None
    if name == "on_hold":
        return row.on_hold_display
    return bool(row.facts[name])


def _matches(row: ComposedRow, filters: Filters, period: tuple[dt.date, dt.date] | None, stage: bool) -> bool:
    facts = row.facts
    if filters.types and facts["molecule_type"] not in filters.types:
        return False
    if filters.classes and (facts["material_class"] or UNKNOWN_CLASS) not in filters.classes:
        return False
    if filters.campaigns and facts["campaign"] not in filters.campaigns:
        return False
    if stage and filters.stages and facts["stage_key"] not in filters.stages:
        return False
    if stage and row.stage_terminal and not filters.wants_released:
        return False
    if filters.bookmarked_keys is not None and row.row_key not in filters.bookmarked_keys:
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
    skip_count: int | None = (
        None  # rows past this stage for which its `applies_if` is false (None: no condition)
    )


class AlertOut(BaseModel):
    kind: Literal["air_gap", "late", "on_hold", "rejected"]
    count: int
    rows: list[RowOut] = []
    detail: dict[str, int] = {}


class OverviewOut(BaseModel):
    freshness: Freshness
    flow_strip: list[FlowEntry]
    on_hold_count: int
    adjusted_count: int  # F16-FR-06: non-released rows with a current adjusted need-by
    total: int
    batch_count: int  # distinct (material, batch) among the shown lots
    mode: Literal["snapshot", "due_in_period"]
    alerts: list[AlertOut]
    bookmarks: list[str]  # every row the current user bookmarked, whatever the filters
    rows: list[RowOut]


def skipped(rows: Sequence[ComposedRow], stage: Stage, order: dict[str, int]) -> int | None:
    """Open lots past ``stage`` that never needed it: its `applies_if` is false for them (F17-FR-04)."""
    if stage.applies_if is None:
        return None
    condition = parse_applies_if(stage.applies_if)
    return sum(
        1
        for row in rows
        if not row.stage_terminal
        and order[row.facts["stage_key"]] > order[stage.key]
        and not condition.evaluate(row.row_facts)
    )


def build_overview(
    rows: Sequence[ComposedRow],
    filters: Filters,
    profile: SiteProfile,
    today: dt.date,
    fresh: Freshness,
    bookmarks: Sequence[str] = (),
) -> OverviewOut:
    labels = {stage.key: stage.label for stage in profile.stages}
    order = {stage.key: number for number, stage in enumerate(profile.stages)}
    shown = select(rows, filters, today)
    unstaged = select(rows, filters, today, with_stage=False)
    flow = [
        FlowEntry(
            stage_key=stage.key,
            label=stage.label,
            count=sum(1 for row in unstaged if row.facts["stage_key"] == stage.key),
            breached=any(row.plan.late for row in unstaged if row.facts["stage_key"] == stage.key),
            late_count=sum(1 for row in unstaged if row.facts["stage_key"] == stage.key and row.plan.late),
            skip_count=skipped(unstaged, stage, order),
        )
        for stage in profile.stages
    ]
    gaps = air_gap_rows(unstaged)
    ud_rejected = sum(1 for row in unstaged if row.facts["ud_rejected"])
    lims_rejected = sum(1 for row in unstaged if row.facts["lims_rejected"])
    on_hold = sum(1 for row in unstaged if row.on_hold_display)
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
        adjusted_count=len(adjusted_rows(unstaged)),
        total=len(shown),
        batch_count=len({(row.facts["material_no"], row.facts["batch_no"]) for row in shown}),
        mode="snapshot" if filters.period == "all" else "due_in_period",
        alerts=alerts,
        bookmarks=list(bookmarks),
        rows=[RowOut.of(row, labels) for row in shown],
    )
