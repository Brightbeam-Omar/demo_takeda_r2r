"""``GET /api/reports/{summary|sla|trends|late|release-rate|adherence}`` and their CSV exports (F20-FR-06).

Every endpoint reads the mirror (and the overrides and the status log) only. The year filters the Executive
Summary, Release Rate and Adherence tabs; SLA Performance, Trends and Late Items are as of the demo date
(OQ-124). Every role may export, and exports are not audited (OQ-126).
"""

import csv
import io
from collections.abc import Callable, Sequence
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response
from r2r_core.profile import SiteProfile
from sqlalchemy.orm import Session

from app_api.auth import current_user
from app_api.db import get_session
from app_api.deps import get_profile
from app_api.services import reports as service
from app_api.services.reports import (
    AdherenceOut,
    Grain,
    LateOut,
    ReleaseRateOut,
    SlaOut,
    StageGrain,
    SummaryOut,
    TrendsOut,
)

router = APIRouter(prefix="/reports", dependencies=[Depends(current_user)])

SessionDep = Annotated[Session, Depends(get_session, scope="function")]
ProfileDep = Annotated[SiteProfile, Depends(get_profile)]
YearQuery = Annotated[int | None, Query(ge=2000, le=2100)]
Tab = Literal["summary", "sla", "trends", "late", "release-rate", "adherence"]


@router.get("/summary")
def summary(session: SessionDep, profile: ProfileDep, year: YearQuery = None) -> SummaryOut:
    return service.summary(session, profile, year)


@router.get("/sla")
def sla(session: SessionDep, profile: ProfileDep, year: YearQuery = None) -> SlaOut:
    return service.sla(session, profile, year)


@router.get("/trends")
def trends(
    session: SessionDep,
    profile: ProfileDep,
    year: YearQuery = None,
    grain: Grain = "weekly",
    stage_grain: StageGrain = "daily",
) -> TrendsOut:
    return service.trends(session, profile, year, grain, stage_grain)


@router.get("/late")
def late(session: SessionDep, profile: ProfileDep, year: YearQuery = None) -> LateOut:
    return service.late(session, profile, year)


@router.get("/release-rate")
def release_rate(session: SessionDep, profile: ProfileDep, year: YearQuery = None) -> ReleaseRateOut:
    return service.release_rate_tab(session, profile, year)


@router.get("/adherence")
def adherence(session: SessionDep, profile: ProfileDep, year: YearQuery = None) -> AdherenceOut:
    return service.adherence_tab(session, profile, year)


# --- exports -----------------------------------------------------------------------------------


def _csv(header: Sequence[str], lines: Sequence[Sequence[object]], filename: str) -> Response:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(header)
    for line in lines:
        writer.writerow(["" if cell is None else cell for cell in line])
    return Response(
        content=out.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _summary_csv(data: SummaryOut) -> Response:
    lines: list[Sequence[object]] = [
        ["Release Rate", data.release.released, data.release.annual_target, data.release.prorata_target,
         data.release.pct_of_prorata, f"{data.release.coverage_weeks} coverage weeks"],
        ["Needs-by Adherence", data.adherence.pct, data.adherence.target_pct, data.adherence.on_time,
         data.adherence.late, f"{data.adherence.excluded} without a need-by"],
        ["Expedite On-Time Rate", data.expedite.pct, data.expedite.target_pct, data.expedite.on_time,
         data.expedite.late, f"{data.expedite.app_only} expedited in the app only"],
    ]  # fmt: skip
    return _csv(
        ("figure", "value", "target", "on_time_or_prorata", "late_or_pct", "note"), lines, "summary.csv"
    )


def _sla_csv(data: SlaOut) -> Response:
    lines = [
        [
            b.metric_id,
            b.label,
            b.status,
            b.week_start,
            b.pct,
            b.completed,
            b.on_time,
            data.target_pct,
            b.null_reason,
        ]
        for b in data.bars
    ]
    header = (
        "metric",
        "label",
        "status",
        "week_start",
        "pct",
        "completed",
        "on_time",
        "target_pct",
        "null_reason",
    )
    return _csv(header, lines, "sla.csv")


def _trends_csv(data: TrendsOut, part: str) -> Response:
    if part == "stage":
        stages = [s.stage_key for s in data.stages]
        lines = [[p.day, *(p.counts.get(k, 0) for k in stages), p.total] for p in data.points]
        return _csv(("day", *stages, "total"), lines, "stage-trends.csv")
    lines = [
        [r.metric_id, r.label, c.period_start, c.pct, c.completed, r.trend, r.trend_delta_pp]
        for r in data.rows
        for c in r.cells
    ]
    return _csv(
        ("metric", "label", "period_start", "pct", "completed", "trend", "trend_delta_pp"),
        lines,
        "trends.csv",
    )


def _late_csv(data: LateOut) -> Response:
    lines = [
        [
            i.material_no,
            i.batch_no,
            i.campaign,
            i.stage_label,
            i.metric_breached,
            i.days_over_sla,
            i.late_reason,
        ]
        for i in data.items
    ]
    header = (
        "material",
        "batch",
        "campaign",
        "current_stage",
        "metric_breached",
        "days_over_sla",
        "late_reason",
    )
    return _csv(header, lines, "late-items.csv")


def _release_csv(data: ReleaseRateOut) -> Response:
    lines = [[w.week_start, w.released_count, data.weekly_target] for w in data.weeks]
    return _csv(("week_start", "released", "weekly_target"), lines, "release-rate.csv")


def _adherence_csv(data: AdherenceOut) -> Response:
    lines = [[w.week_start, w.within, w.exceeded] for w in data.weeks]
    return _csv(("week_start", "within_needs_by", "exceeded_needs_by"), lines, "adherence.csv")


@router.get("/{tab}/export.csv")
def export(
    tab: Tab,
    session: SessionDep,
    profile: ProfileDep,
    year: YearQuery = None,
    grain: Grain = "weekly",
    stage_grain: StageGrain = "daily",
    part: Literal["sla", "stage"] = "sla",
) -> Response:
    """The figures behind the tab. Trends exports the SLA table, or the stage series with ``part=stage``."""
    builders: dict[str, Callable[[], Response]] = {
        "summary": lambda: _summary_csv(service.summary(session, profile, year)),
        "sla": lambda: _sla_csv(service.sla(session, profile, year)),
        "trends": lambda: _trends_csv(service.trends(session, profile, year, grain, stage_grain), part),
        "late": lambda: _late_csv(service.late(session, profile, year)),
        "release-rate": lambda: _release_csv(service.release_rate_tab(session, profile, year)),
        "adherence": lambda: _adherence_csv(service.adherence_tab(session, profile, year)),
    }
    return builders[tab]()
