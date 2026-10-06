"""The Reports & Metrics read model (F20-FR-06): the mirror, read through ``r2r_core.reports``.

Nothing here computes a metric percentage (the pipeline owns them, constitution P2). The figures that
depend on human input or on "now" come from ``r2r_core.reports``; this module only loads the inputs and
shapes them for the six tabs and their CSV exports.
"""

import datetime as dt
from collections import defaultdict
from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from pydantic import BaseModel
from r2r_core import clock
from r2r_core.profile import SiteProfile
from r2r_core.reports import (
    Adherence,
    ExpediteResult,
    LateCandidate,
    LogEntry,
    NeedByVersion,
    ReleasedLot,
    ReleaseRate,
    adherence_by_week,
    coverage,
    expedite_on_time,
    late_items,
    needs_by_adherence,
    release_rate,
    stage_metric_map,
    trend,
)
from sqlalchemy import text
from sqlalchemy.orm import Session

from app_api.routers.metrics import metric_rag
from app_api.schemas import Freshness
from app_api.services.store import Composed, freshness, load_composed

Grain = Literal["weekly", "monthly"]
StageGrain = Literal["daily", "weekly"]
WEEKLY_CELLS = 4  # complete weeks shown before the current one
MONTHLY_CELLS = 3  # complete months shown before the current one


# --- shapes ------------------------------------------------------------------------------------


class AwaitingMetric(BaseModel):
    metric_id: str
    label: str
    null_reason: str | None


class ReportMeta(BaseModel):
    freshness: Freshness
    year: int
    years: list[int]
    coverage_from: dt.date | None
    awaiting_signal: list[AwaitingMetric]


class ReleaseCard(BaseModel):
    released: int
    annual_target: int
    prorata_target: int
    pct_of_prorata: int | None
    coverage_weeks: int


class AdherenceCard(BaseModel):
    on_time: int
    late: int
    excluded: int
    pct: Decimal | None
    target_pct: int
    rag: str | None


class ExpediteCard(BaseModel):
    on_time: int
    late: int
    expedited: int
    app_only: int
    pct: Decimal | None
    target_pct: int
    rag: str | None


class SummaryOut(ReportMeta):
    release: ReleaseCard
    adherence: AdherenceCard
    expedite: ExpediteCard


class SlaBar(BaseModel):
    metric_id: str
    label: str
    stage_label: str | None
    status: str
    null_reason: str | None
    week_start: dt.date | None
    pct: Decimal | None
    completed: int
    on_time: int
    rag: str | None


class SlaOut(ReportMeta):
    target_pct: int
    bars: list[SlaBar]


class TrendCell(BaseModel):
    period_start: dt.date
    pct: Decimal | None
    completed: int
    rag: str | None


class TrendRow(BaseModel):
    metric_id: str
    label: str
    status: str
    null_reason: str | None
    cells: list[TrendCell]
    trend: str  # up | down | stable | none
    trend_delta_pp: Decimal | None


class StageInfo(BaseModel):
    stage_key: str
    label: str
    sort: int


class StagePoint(BaseModel):
    day: dt.date  # the day counted: every day, or the Sunday ending the week (the snapshot day for this week)
    week_start: dt.date | None
    counts: dict[str, int]
    total: int


class TrendsOut(ReportMeta):
    grain: Grain
    stage_grain: StageGrain
    periods: list[dt.date]
    rows: list[TrendRow]
    stages: list[StageInfo]
    points: list[StagePoint]


class LateRow(BaseModel):
    row_key: str
    material_no: str
    material_desc: str | None
    batch_no: str
    campaign: str | None
    stage_key: str
    stage_label: str
    metric_breached: str | None
    days_over_sla: int
    late_reason: str | None


class LateOut(ReportMeta):
    count: int
    items: list[LateRow]


class ReleaseWeek(BaseModel):
    week_start: dt.date
    released_count: int


class ReleaseRateOut(ReportMeta):
    weekly_target: int
    weeks: list[ReleaseWeek]
    release: ReleaseCard


class AdherenceWeek(BaseModel):
    week_start: dt.date
    within: int
    exceeded: int


class AdherenceOut(ReportMeta):
    weeks: list[AdherenceWeek]
    adherence: AdherenceCard


# --- inputs ------------------------------------------------------------------------------------


def released_lots(session: Session) -> list[ReleasedLot]:
    rows = session.execute(
        text(
            "SELECT row_key, ud_date, ud_effective, need_by_at_release, expedite_due_date "
            "FROM mirror_batch_pipeline WHERE ud_effective AND ud_date IS NOT NULL ORDER BY row_key"
        )
    )
    return [ReleasedLot(r.row_key, r.ud_date, True, r.need_by_at_release, r.expedite_due_date) for r in rows]


def need_by_versions(session: Session, profile: SiteProfile) -> list[NeedByVersion]:
    """Every version of the need-by override, oldest first (OQ-121)."""
    rows = session.execute(
        text(
            "SELECT row_key, value_json, created_at FROM override_value "
            "WHERE field = 'adjusted_need_by_date' ORDER BY id"
        )
    )
    return [
        NeedByVersion(
            r.row_key,
            dt.date.fromisoformat(r.value_json) if r.value_json is not None else None,
            r.created_at.astimezone(profile.site.tz).date(),
        )
        for r in rows
    ]


def app_expedited(session: Session) -> set[str]:
    rows = session.execute(
        text(
            "SELECT row_key FROM override_value "
            "WHERE field = 'expedite' AND is_current AND value_json = 'true'"
        )
    )
    return {r.row_key for r in rows}


def _metric_reference(session: Session) -> list[dict[str, object]]:
    return [
        dict(r)
        for r in session.execute(text("SELECT * FROM mirror_metric_reference ORDER BY metric_id")).mappings()
    ]


def meta(session: Session, profile: SiteProfile, year: int | None, lots: Sequence[ReleasedLot]) -> ReportMeta:
    now = clock.now()
    today = now.astimezone(profile.site.tz).date()
    chosen = year if year is not None else today.year
    years = {lot.ud_date.year for lot in lots if lot.ud_date is not None}
    years |= {
        r.year
        for r in session.execute(
            text(
                "SELECT DISTINCT extract(year FROM week_start)::int AS year "
                "FROM mirror_weekly_metrics WHERE completed > 0"
            )
        )
    }
    years.add(today.year)
    start, _ = coverage(lots, chosen, today)
    awaiting = [
        AwaitingMetric(
            metric_id=str(r["metric_id"]), label=str(r["label"]), null_reason=_text(r["null_reason"])
        )
        for r in _metric_reference(session)
        if r["status"] == "awaiting_signal"
    ]
    return ReportMeta(
        freshness=freshness(session, now),
        year=chosen,
        years=sorted(years, reverse=True),
        coverage_from=start,
        awaiting_signal=awaiting,
    )


def _text(value: object) -> str | None:
    return None if value is None else str(value)


def _adherence_rag(pct: Decimal | None, target: int) -> str | None:
    """Green at the target, amber within 10 points below it, otherwise red."""
    if pct is None:
        return None
    if pct >= target:
        return "green"
    return "amber" if pct >= target - 10 else "red"


def release_card(result: ReleaseRate) -> ReleaseCard:
    return ReleaseCard(
        released=result.released,
        annual_target=result.annual_target,
        prorata_target=int(result.prorata_target.quantize(Decimal(1), rounding=ROUND_HALF_UP)),
        pct_of_prorata=result.pct_of_prorata,
        coverage_weeks=result.coverage_weeks,
    )


def adherence_card(result: Adherence, profile: SiteProfile) -> AdherenceCard:
    target = profile.targets.needs_by_adherence_pct
    return AdherenceCard(
        on_time=result.on_time,
        late=result.late,
        excluded=result.excluded,
        pct=result.pct,
        target_pct=target,
        rag=_adherence_rag(result.pct, target),
    )


def expedite_card(result: ExpediteResult, profile: SiteProfile) -> ExpediteCard:
    target = profile.targets.expedite_on_time_pct
    return ExpediteCard(
        on_time=result.on_time,
        late=result.late,
        expedited=result.expedited,
        app_only=result.app_only,
        pct=result.pct,
        target_pct=target,
        rag=_adherence_rag(result.pct, target),
    )


# --- tabs --------------------------------------------------------------------------------------


def summary(session: Session, profile: SiteProfile, year: int | None) -> SummaryOut:
    lots = released_lots(session)
    base = meta(session, profile, year, lots)
    today = clock.now().astimezone(profile.site.tz).date()
    versions = need_by_versions(session, profile)
    return SummaryOut(
        **base.model_dump(),
        release=release_card(release_rate(lots, base.year, today, profile.targets.release_annual)),
        adherence=adherence_card(needs_by_adherence(lots, versions, base.year), profile),
        expedite=expedite_card(expedite_on_time(lots, app_expedited(session), base.year), profile),
    )


def _monday(day: dt.date) -> dt.date:
    return day - dt.timedelta(days=day.weekday())


def _add_months(first: dt.date, months: int) -> dt.date:
    index = first.year * 12 + first.month - 1 + months
    return dt.date(index // 12, index % 12 + 1, 1)


def sla(session: Session, profile: SiteProfile, year: int | None) -> SlaOut:
    base = meta(session, profile, year, released_lots(session))
    today = clock.now().astimezone(profile.site.tz).date()
    last_complete = _monday(today) - dt.timedelta(weeks=1)
    weeks = {
        (r.metric_id, r.week_start): r
        for r in session.execute(
            text("SELECT metric_id, week_start, completed, on_time, pct FROM mirror_weekly_metrics")
        )
    }
    stage_labels = {s.key: s.label for s in profile.stages}
    bars = []
    for ref in _metric_reference(session):
        active = ref["status"] == "active"
        week = weeks.get((str(ref["metric_id"]), last_complete)) if active else None
        pct = week.pct if week is not None else None
        bars.append(
            SlaBar(
                metric_id=str(ref["metric_id"]),
                label=str(ref["label"]),
                stage_label=stage_labels.get(str(ref["stage_key"])) if ref["stage_key"] else None,
                status=str(ref["status"]),
                null_reason=_text(ref["null_reason"]),
                week_start=last_complete if active else None,
                pct=pct,
                completed=week.completed if week is not None else 0,
                on_time=week.on_time if week is not None else 0,
                rag=metric_rag(pct, profile),
            )
        )
    return SlaOut(**base.model_dump(), target_pct=profile.metric_rag.green_min_pct, bars=bars)


def _periods(grain: Grain, today: dt.date) -> list[dt.date]:
    if grain == "weekly":
        current = _monday(today)
        return [current - dt.timedelta(weeks=n) for n in range(WEEKLY_CELLS, -1, -1)]
    current_month = today.replace(day=1)
    return [_add_months(current_month, -n) for n in range(MONTHLY_CELLS, -1, -1)]


def trends(
    session: Session, profile: SiteProfile, year: int | None, grain: Grain, stage_grain: StageGrain
) -> TrendsOut:
    base = meta(session, profile, year, released_lots(session))
    today = clock.now().astimezone(profile.site.tz).date()
    periods = _periods(grain, today)
    table, column = (
        ("mirror_weekly_metrics", "week_start")
        if grain == "weekly"
        else ("mirror_monthly_metrics", "month_start")
    )
    cells = {
        (r.metric_id, r.period): r
        for r in session.execute(
            text(f"SELECT metric_id, {column} AS period, completed, pct FROM {table}")  # fixed table names
        )
    }
    rows = []
    for ref in _metric_reference(session):
        metric_id = str(ref["metric_id"])
        active = ref["status"] == "active"
        series = [
            TrendCell(
                period_start=period,
                pct=found.pct if found else None,
                completed=found.completed if found else 0,
                rag=metric_rag(found.pct if found else None, profile),
            )
            for period in periods
            for found in [cells.get((metric_id, period)) if active else None]
        ]
        # The trend compares the last complete period with the one before it (the current one is partial).
        change = trend(series[-2].pct, series[-3].pct)
        rows.append(
            TrendRow(
                metric_id=metric_id,
                label=str(ref["label"]),
                status=str(ref["status"]),
                null_reason=_text(ref["null_reason"]),
                cells=series,
                trend=change.direction,
                trend_delta_pp=change.delta_pp,
            )
        )
    stages = [
        StageInfo(stage_key=s.key, label=s.label, sort=number)
        for number, s in enumerate(profile.stages, start=1)
        if not s.terminal and s.sla_days > 0
    ]
    return TrendsOut(
        **base.model_dump(),
        grain=grain,
        stage_grain=stage_grain,
        periods=periods,
        rows=rows,
        stages=stages,
        points=stage_points(session, stage_grain),
    )


def stage_points(session: Session, stage_grain: StageGrain) -> list[StagePoint]:
    """Open lots per stage per day, or on the Sunday ending each week (the snapshot day for this week)."""
    by_day: dict[dt.date, dict[str, int]] = defaultdict(dict)
    for r in session.execute(
        text("SELECT day, stage_key, open_count FROM mirror_pipeline_daily ORDER BY day")
    ):
        by_day[r.day][r.stage_key] = r.open_count
    days = sorted(by_day)
    if stage_grain == "daily":
        return [
            StagePoint(day=d, week_start=None, counts=by_day[d], total=sum(by_day[d].values())) for d in days
        ]
    last = days[-1] if days else None
    points = []
    for d in days:
        sunday = d == _monday(d) + dt.timedelta(days=6)
        if sunday or d == last:
            points.append(
                StagePoint(day=d, week_start=_monday(d), counts=by_day[d], total=sum(by_day[d].values()))
            )
    return points


def late(session: Session, profile: SiteProfile, year: int | None) -> LateOut:
    base = meta(session, profile, year, released_lots(session))
    composed: Composed = load_composed(session, profile)
    candidates = [
        LateCandidate(
            row.row_key,
            str(row.facts["material_no"]),
            str(row.facts["batch_no"]),
            row.facts["campaign"],
            str(row.facts["stage_key"]),
            row.plan,
        )
        for row in composed.rows
        if row.plan.late
    ]
    log: dict[str, list[LogEntry]] = defaultdict(list)
    for r in session.execute(
        text("SELECT row_key, reason_code, id FROM status_log WHERE reason_code IS NOT NULL ORDER BY id")
    ):
        log[r.row_key].append(LogEntry(r.reason_code, r.id))
    code_labels = {
        r.code: r.label for r in session.execute(text("SELECT code, label FROM mirror_reason_codes"))
    }
    reasons = {r.key: r.label for r in profile.status_reasons}
    labels = {s.key: s.label for s in profile.stages}
    descriptions = {row.row_key: row.facts["material_desc"] for row in composed.rows}
    items = [
        LateRow(
            row_key=i.row_key,
            material_no=i.material_no,
            material_desc=descriptions.get(i.row_key),
            batch_no=i.batch_no,
            campaign=i.campaign,
            stage_key=i.stage_key,
            stage_label=labels.get(i.stage_key, i.stage_key),
            metric_breached=i.metric_breached,
            days_over_sla=i.days_over_sla,
            late_reason=i.late_reason,
        )
        for i in late_items(candidates, log, stage_metric_map(profile), reasons, code_labels)
    ]
    return LateOut(**base.model_dump(), count=len(items), items=items)


def _in_year(week_start: dt.date, year: int) -> bool:
    """An ISO week belongs to the year of its Thursday."""
    return (week_start + dt.timedelta(days=3)).year == year


def release_rate_tab(session: Session, profile: SiteProfile, year: int | None) -> ReleaseRateOut:
    lots = released_lots(session)
    base = meta(session, profile, year, lots)
    today = clock.now().astimezone(profile.site.tz).date()
    weeks = [
        ReleaseWeek(week_start=r.week_start, released_count=r.released_count)
        for r in session.execute(
            text("SELECT week_start, released_count FROM mirror_releases_weekly ORDER BY week_start")
        )
        if _in_year(r.week_start, base.year)
        and r.week_start < _monday(today)  # the week to date is not a week
    ]
    return ReleaseRateOut(
        **base.model_dump(),
        weekly_target=profile.targets.release_weekly,
        weeks=weeks,
        release=release_card(release_rate(lots, base.year, today, profile.targets.release_annual)),
    )


def adherence_tab(session: Session, profile: SiteProfile, year: int | None) -> AdherenceOut:
    lots = released_lots(session)
    base = meta(session, profile, year, lots)
    versions = need_by_versions(session, profile)
    return AdherenceOut(
        **base.model_dump(),
        weeks=[
            AdherenceWeek(week_start=w, within=a, exceeded=b)
            for w, a, b in adherence_by_week(lots, versions, base.year)
        ],
        adherence=adherence_card(needs_by_adherence(lots, versions, base.year), profile),
    )
