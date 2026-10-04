"""Plan-date maths: the business logic of the demo (03-domain-model section 5).

Pure functions only: no I/O, no clock reads. "Today" is always passed in. Nothing else in the system may
implement this maths (constitution P2).
"""

import datetime as dt
import functools
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from r2r_core.applies_if import parse_applies_if
from r2r_core.domain import LotType, Rag, RowFacts, StageKey
from r2r_core.profile import SiteProfile

EXPEDITE_PREFIX = "EXPEDITE_"
PULLED_FORWARD = "CAMPAIGN_PULLED_FORWARD"

_condition = functools.cache(parse_applies_if)


def _applies(condition: str | None, row: RowFacts) -> bool:
    return condition is None or _condition(condition).evaluate(row)


def applicable_stages(row: RowFacts, profile: SiteProfile) -> list[StageKey]:
    """Stages the row passes through, in profile order (03 section 4, "Applicable stages").

    A stage takes part in SLA maths only if it has ``sla_days > 0``, is not terminal, and its
    ``applies_if`` condition (if any) holds for the row. No stage key is hard-coded.
    """
    return [
        StageKey(stage.key)
        for stage in profile.stages
        if stage.sla_days > 0 and not stage.terminal and _applies(stage.applies_if, row)
    ]


def sla_for(stage: StageKey, lot_type: LotType, profile: SiteProfile) -> int:
    """SLA days for a stage: the profile value, overridden for re-evaluation lots where given."""
    base = profile.stage(stage).sla_days
    if lot_type == LotType.REEVAL:
        return profile.reeval_sla_overrides.get(stage, base)
    return base


@dataclass(frozen=True)
class AdjustedNeedBy:
    """A human override of the need-by date, with its reason code (held in the app database)."""

    date: dt.date
    reason_code: str


@dataclass(frozen=True)
class PlanResult:
    expected_completion: dt.date | None
    must_complete_by: dict[StageKey, dt.date] = field(default_factory=dict)  # remaining stages, in order
    compressed: bool = False
    compression_ratio: Decimal | None = None
    effective_slas: dict[StageKey, int] = field(default_factory=dict)  # remaining stages, in order
    days_in_stage: int | None = None
    days_remaining: int | None = None
    rag: Rag | None = None
    late: bool = False
    late_reason_auto: str | None = None


def operative_need_by(row: RowFacts, adjusted: AdjustedNeedBy | None) -> dt.date | None:
    """The adjusted date replaces the locked system date completely (03 section 5.1)."""
    return adjusted.date if adjusted is not None else row.system_need_by_locked


def _round_half_up(numerator: int, denominator: int) -> int:
    """``numerator / denominator`` rounded half up, in exact arithmetic (never Python's ``round``)."""
    return int((Decimal(numerator) / Decimal(denominator)).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def _effective_slas(slas: list[int], available: int) -> tuple[list[int], bool, Decimal | None]:
    """Apply proportional compression (03 section 5.2). Returns (slas, compressed, ratio)."""
    budget = sum(slas)
    if available >= budget:
        return slas, False, None
    if available > 0:
        compressed = [max(1, _round_half_up(sla * available, budget)) for sla in slas]
        return compressed, True, Decimal(available) / Decimal(budget)
    return [1] * len(slas), True, None  # already late: every stage squeezed to the one-day floor


def _rag(days_remaining: int, profile: SiteProfile) -> Rag:
    if days_remaining < 0:
        return Rag.RED
    if days_remaining < profile.rag.amber_days_remaining_lt:
        return Rag.AMBER
    return Rag.GREEN


def _auto_late_reason(row: RowFacts, adjusted: AdjustedNeedBy | None, late: bool) -> str | None:
    """03 section 5.4: a pull-forward or expedite explains lateness that the process did not cause."""
    if not late or adjusted is None or row.system_need_by_locked is None:
        return None
    qualifies = adjusted.reason_code == PULLED_FORWARD or adjusted.reason_code.startswith(EXPEDITE_PREFIX)
    return adjusted.reason_code if qualifies and adjusted.date < row.system_need_by_locked else None


def plan(
    row: RowFacts, profile: SiteProfile, today: dt.date, adjusted: AdjustedNeedBy | None = None
) -> PlanResult:
    """Expected completion of the current stage, RAG and late flags (03 section 5.2 to 5.4).

    ``remaining`` is the row's applicable stages from the current one to the last. ``B`` is the sum of their
    SLAs, ``E`` the current stage entry date and ``N`` the operative need-by date.

    * No ``N``: forward. Each stage ends its SLA after the previous one.
    * ``A = N - E >= B``: backward from ``N`` with the full SLAs.
    * ``0 < A < B``: backward with SLAs compressed by ``A / B``, each rounded half up and floored at 1 day.
    * ``A <= 0``: backward with every stage at 1 day (the row is already late).

    Because of the 1-day floor, the compressed SLAs can add up to more than ``A`` when ``A`` is very small,
    which pushes ``expected_completion`` before the entry date. Late and RAG then follow from the dates as
    computed.

    Rows with nothing to plan (a stage that takes no part in SLA maths, or a started stage with no entry
    date) get ``expected_completion = None``, no RAG and ``late = False``. A stage that exists but does not
    apply to the row raises ``ValueError``; an unknown stage raises ``KeyError``.
    """
    entry = row.current_stage_entry_date
    days_in_stage = (today - entry).days if entry is not None else None
    stages = applicable_stages(row, profile)
    if row.stage_key not in stages:
        stage = profile.stage(row.stage_key)  # unknown stage: KeyError
        if stage.sla_days > 0 and not stage.terminal:
            raise ValueError(f"stage {row.stage_key!r} does not apply to row {row.row_key}")
        return PlanResult(expected_completion=None, days_in_stage=days_in_stage)
    if entry is None:
        return PlanResult(expected_completion=None)

    remaining = stages[stages.index(row.stage_key) :]
    slas = [sla_for(stage, row.lot_type, profile) for stage in remaining]
    need_by = operative_need_by(row, adjusted)

    ratio: Decimal | None = None
    compressed = False
    if need_by is None:
        effective = slas
        deadlines: list[dt.date] = []
        cursor = entry
        for sla in effective:
            cursor += dt.timedelta(days=sla)
            deadlines.append(cursor)
    else:
        effective, compressed, ratio = _effective_slas(slas, (need_by - entry).days)
        deadlines = [need_by]
        for later_sla in reversed(effective[1:]):
            deadlines.append(deadlines[-1] - dt.timedelta(days=later_sla))
        deadlines.reverse()

    expected = deadlines[0]
    days_remaining = (expected - today).days
    rag = _rag(days_remaining, profile)
    late = rag == Rag.RED
    return PlanResult(
        expected_completion=expected,
        must_complete_by=dict(zip(remaining, deadlines, strict=True)),
        compressed=compressed,
        compression_ratio=ratio,
        effective_slas=dict(zip(remaining, effective, strict=True)),
        days_in_stage=days_in_stage,
        days_remaining=days_remaining,
        rag=rag,
        late=late,
        late_reason_auto=_auto_late_reason(row, adjusted, late),
    )
