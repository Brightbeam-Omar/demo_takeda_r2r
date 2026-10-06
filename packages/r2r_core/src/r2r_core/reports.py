"""Read-time report maths for the Reports & Metrics page (F20-FR-03, 03-domain-model section 7.1).

Pure functions only: no I/O, no clock reads. "Today" and the year are passed in. The pipeline owns the metric
percentages (03 section 7); this module owns the figures that depend on human input or on "now": release rate,
needs-by adherence, expedite on-time and late items.
"""

from collections import defaultdict
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from r2r_core.profile import SiteProfile
from r2r_core.sla import PlanResult

STABLE_BAND_PP = Decimal(2)  # |change| below this many percentage points is "Stable"
WEEKS_PER_YEAR = 52


@dataclass(frozen=True)
class ReleasedLot:
    """The published facts of one lot that the release figures read (a row of ``batch_pipeline_v``)."""

    row_key: str
    ud_date: date | None
    ud_effective: bool
    need_by_at_release: date | None
    expedite_due_date: date | None


@dataclass(frozen=True)
class NeedByVersion:
    """One version of the ``adjusted_need_by_date`` override; ``value`` is None for a clear."""

    row_key: str
    value: date | None
    created_on: date  # the version's creation, as a site-local date


def _released_in(rows: Sequence[ReleasedLot], year: int) -> list[ReleasedLot]:
    return [r for r in rows if r.ud_effective and r.ud_date is not None and r.ud_date.year == year]


def _monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _pct(part: int, whole: int) -> Decimal | None:
    if whole == 0:
        return None
    return (Decimal(100) * part / whole).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


# --- release rate (OQ-117) ---------------------------------------------------------------------


def coverage(rows: Sequence[ReleasedLot], year: int, today: date) -> tuple[date | None, int]:
    """``(first release date of the year, whole ISO weeks covered)``.

    Coverage starts at the year's earliest effective ``ud_date`` and runs to the snapshot week, or to the end
    of the year for a past year. The week count is inclusive of both weeks and capped at 52.
    """
    released = _released_in(rows, year)
    if not released:
        return None, 0
    first = min(r.ud_date for r in released if r.ud_date is not None)
    end = min(today, date(year, 12, 31))
    weeks = (_monday(end) - _monday(first)).days // 7 + 1
    return first, min(weeks, WEEKS_PER_YEAR)


@dataclass(frozen=True)
class ReleaseRate:
    released: int
    annual_target: int
    prorata_target: Decimal
    pct_of_prorata: int | None  # whole percent of the pro-rata target
    coverage_start: date | None
    coverage_weeks: int


def release_rate(rows: Sequence[ReleasedLot], year: int, today: date, annual_target: int) -> ReleaseRate:
    released = len(_released_in(rows, year))
    start, weeks = coverage(rows, year, today)
    prorata = Decimal(annual_target) * weeks / WEEKS_PER_YEAR
    share = None
    if prorata > 0:
        share = int((Decimal(100) * released / prorata).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    return ReleaseRate(released, annual_target, prorata, share, start, weeks)


# --- needs-by adherence (OQ-119, OQ-121) -------------------------------------------------------


def _need_by(lot: ReleasedLot, versions: Mapping[str, list[NeedByVersion]]) -> date | None:
    """The need-by a lot was measured against: the latest override version created on or before the release
    replaces ``need_by_at_release`` completely; a clear falls back to it."""
    assert lot.ud_date is not None
    applicable = [v for v in versions.get(lot.row_key, []) if v.created_on <= lot.ud_date]
    if applicable and applicable[-1].value is not None:
        return applicable[-1].value
    return lot.need_by_at_release


def _versions_by_row(versions: Sequence[NeedByVersion]) -> dict[str, list[NeedByVersion]]:
    """Versions of each row, oldest first (input order is creation order)."""
    grouped: dict[str, list[NeedByVersion]] = defaultdict(list)
    for version in versions:
        grouped[version.row_key].append(version)
    return grouped


@dataclass(frozen=True)
class Adherence:
    on_time: int
    late: int
    excluded: int  # released lots with no need-by at all
    total: int  # released lots in the year
    pct: Decimal | None


def needs_by_adherence(
    rows: Sequence[ReleasedLot], versions: Sequence[NeedByVersion], year: int
) -> Adherence:
    by_row = _versions_by_row(versions)
    on_time = late = excluded = 0
    released = _released_in(rows, year)
    for lot in released:
        need_by = _need_by(lot, by_row)
        if need_by is None:
            excluded += 1
        elif lot.ud_date is not None and lot.ud_date <= need_by:
            on_time += 1
        else:
            late += 1
    return Adherence(on_time, late, excluded, len(released), _pct(on_time, on_time + late))


def adherence_by_week(
    rows: Sequence[ReleasedLot], versions: Sequence[NeedByVersion], year: int
) -> list[tuple[date, int, int]]:
    """``(week_start, within, exceeded)`` per ISO week of the release date, for lots that have a need-by."""
    by_row = _versions_by_row(versions)
    counts: dict[date, list[int]] = defaultdict(lambda: [0, 0])
    for lot in _released_in(rows, year):
        need_by = _need_by(lot, by_row)
        if need_by is None or lot.ud_date is None:
            continue
        counts[_monday(lot.ud_date)][0 if lot.ud_date <= need_by else 1] += 1
    return [(week, within, exceeded) for week, (within, exceeded) in sorted(counts.items())]


# --- expedite on-time (OQ-120) -----------------------------------------------------------------


@dataclass(frozen=True)
class ExpediteResult:
    on_time: int
    late: int
    expedited: int  # released lots with a source due date (on_time + late)
    app_only: int  # released lots expedited in the app only: no due date, so not in the ratio
    pct: Decimal | None


def expedite_on_time(
    rows: Sequence[ReleasedLot], app_expedited: Collection[str], year: int
) -> ExpediteResult:
    on_time = late = app_only = 0
    for lot in _released_in(rows, year):
        if lot.expedite_due_date is None:
            app_only += lot.row_key in app_expedited
        elif lot.ud_date is not None and lot.ud_date <= lot.expedite_due_date:
            on_time += 1
        else:
            late += 1
    return ExpediteResult(on_time, late, on_time + late, app_only, _pct(on_time, on_time + late))


# --- trend (OQ-126) ----------------------------------------------------------------------------


@dataclass(frozen=True)
class Trend:
    direction: str  # up | down | stable | none
    delta_pp: Decimal | None


def trend(last: Decimal | None, previous: Decimal | None) -> Trend:
    """The change in percentage points from the previous period to the last complete one."""
    if last is None or previous is None:
        return Trend("none", None)
    delta = last - previous
    if abs(delta) < STABLE_BAND_PP:
        return Trend("stable", delta)
    return Trend("up" if delta > 0 else "down", delta)


# --- late items (OQ-123) -----------------------------------------------------------------------


@dataclass(frozen=True)
class LateCandidate:
    row_key: str
    material_no: str
    batch_no: str
    campaign: str | None
    stage_key: str
    plan: PlanResult


@dataclass(frozen=True)
class LogEntry:
    """One status-log entry of a row. A higher ``order`` is newer."""

    reason_key: str | None
    order: int


@dataclass(frozen=True)
class LateItem:
    row_key: str
    material_no: str
    batch_no: str
    campaign: str | None
    stage_key: str
    metric_breached: str | None
    days_over_sla: int
    late_reason: str | None


def stage_metric_map(profile: SiteProfile) -> dict[str, str]:
    """The metric bound to each stage (M1, M2 and M4 included, although they have no signal yet)."""
    return {m.stage: m.id for m in profile.metrics if m.stage is not None}


def _late_reason(
    candidate: LateCandidate,
    log: Sequence[LogEntry],
    status_reasons: Mapping[str, str],
    code_labels: Mapping[str, str],
) -> str | None:
    with_reason = [e for e in log if e.reason_key is not None]
    if with_reason:
        key = max(with_reason, key=lambda e: e.order).reason_key
        assert key is not None
        return status_reasons.get(key, key)
    auto = candidate.plan.late_reason_auto
    if auto is not None:
        return code_labels.get(auto, auto)
    return None


def late_items(
    candidates: Sequence[LateCandidate],
    status_log: Mapping[str, Sequence[LogEntry]],
    stage_metric: Mapping[str, str],
    status_reasons: Mapping[str, str],
    code_labels: Mapping[str, str],
) -> list[LateItem]:
    """Rows that are late now, worst first. Days over SLA is ``-days_remaining`` (the Overview's LATE +Nd)."""
    items = [
        LateItem(
            row_key=c.row_key,
            material_no=c.material_no,
            batch_no=c.batch_no,
            campaign=c.campaign,
            stage_key=c.stage_key,
            metric_breached=stage_metric.get(c.stage_key),
            days_over_sla=-c.plan.days_remaining,
            late_reason=_late_reason(c, status_log.get(c.row_key, []), status_reasons, code_labels),
        )
        for c in candidates
        if c.plan.late and c.plan.days_remaining is not None
    ]
    return sorted(items, key=lambda i: (-i.days_over_sla, i.material_no, i.batch_no, i.row_key))
