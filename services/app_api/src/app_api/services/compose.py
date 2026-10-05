"""Row composition (F09-FR-01): a mirror row, plus its current overrides, through ``r2r_core.sla``.

Pure: no database, no clock. The caller passes the mirror rows as dicts (published column names), the current
override values and comment counts per ``row_key``, the profile and "now". The plan dates come only from
``r2r_core.sla`` and the air gap only from ``r2r_core.airgap`` (constitution P2).
"""

import datetime as dt
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from r2r_core.airgap import air_gap
from r2r_core.domain import LotType, RowFacts, StageKey
from r2r_core.profile import SiteProfile
from r2r_core.sla import AdjustedNeedBy, Flags, PlanResult, exception_sort_key, operative_need_by, plan

ADJUSTED = "adjusted_need_by_date"
EXPEDITE = "expedite"
MANUAL_STATUS = "manual_status"


@dataclass(frozen=True)
class CurrentOverride:
    """The current version of one override field."""

    value: Any
    reason_code: str | None
    note: str | None
    version: int
    author: str
    created_at: dt.datetime


@dataclass(frozen=True)
class ComposedRow:
    facts: Mapping[str, Any]
    row_facts: RowFacts
    plan: PlanResult
    adjusted: AdjustedNeedBy | None
    operative_need_by: dt.date | None
    expedite: bool
    manual_status: Mapping[str, Any] | None
    air_gap: bool
    air_gap_hours: int
    stage_terminal: bool
    comment_count: int
    overrides: Mapping[str, CurrentOverride] = field(default_factory=dict)

    @property
    def row_key(self) -> str:
        return str(self.facts["row_key"])

    @property
    def flags(self) -> Flags:
        return Flags(
            ud_rejected=bool(self.facts["ud_rejected"]),
            on_hold=bool(self.facts["on_hold"]),
            air_gap=self.air_gap,
        )

    @property
    def sort_key(self) -> tuple[int, int, str, str]:
        return exception_sort_key(self.row_facts, self.plan, self.flags)


def row_facts(facts: Mapping[str, Any]) -> RowFacts:
    return RowFacts(
        row_key=facts["row_key"],
        stage_key=StageKey(facts["stage_key"]),
        lot_type=LotType(facts["lot_type"]),
        received_location_type=facts["received_location_type"] or "",
        offsite=bool(facts["offsite"]),
        current_stage_entry_date=facts["current_stage_entry_date"],
        system_need_by_locked=facts["system_need_by_locked"],
        on_hold=bool(facts["on_hold"]),
        ud_rejected=bool(facts["ud_rejected"]),
        lims_status=facts["lims_status"] or "none",
        ud_effective=bool(facts["ud_effective"]),
        ud_code=facts["ud_code"],
        lims_approved_at=facts["lims_approved_at"],
    )


def adjusted_need_by(overrides: Mapping[str, CurrentOverride]) -> AdjustedNeedBy | None:
    current = overrides.get(ADJUSTED)
    if current is None or current.value is None:
        return None
    return AdjustedNeedBy(date=dt.date.fromisoformat(current.value), reason_code=current.reason_code or "")


def compose_row(
    facts: Mapping[str, Any],
    overrides: Mapping[str, CurrentOverride],
    comment_count: int,
    profile: SiteProfile,
    now: dt.datetime,
) -> ComposedRow:
    base = row_facts(facts)
    adjusted = adjusted_need_by(overrides)
    today = now.astimezone(profile.site.tz).date()
    gap, hours = air_gap(
        base.lims_status,
        base.ud_code,
        base.lims_approved_at,
        now,
        profile.air_gap.threshold_hours,
        facts["erp_results_recorded_at"],
    )
    expedite = overrides.get(EXPEDITE)
    status = overrides.get(MANUAL_STATUS)
    return ComposedRow(
        facts=facts,
        row_facts=base,
        plan=plan(base, profile, today, adjusted),
        adjusted=adjusted,
        operative_need_by=operative_need_by(base, adjusted),
        expedite=bool(expedite and expedite.value),
        manual_status=status.value if status is not None and status.value is not None else None,
        air_gap=gap,
        air_gap_hours=hours,
        stage_terminal=profile.stage(base.stage_key).terminal,
        comment_count=comment_count,
        overrides=overrides,
    )


def compose_rows(
    mirror_rows: Iterable[Mapping[str, Any]],
    overrides: Mapping[str, Mapping[str, CurrentOverride]],
    comment_counts: Mapping[str, int],
    profile: SiteProfile,
    now: dt.datetime,
) -> list[ComposedRow]:
    return [
        compose_row(
            row, overrides.get(row["row_key"], {}), comment_counts.get(row["row_key"], 0), profile, now
        )
        for row in mirror_rows
    ]
