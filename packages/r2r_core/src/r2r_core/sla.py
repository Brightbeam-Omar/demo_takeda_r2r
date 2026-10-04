"""Plan-date maths: the business logic of the demo (03-domain-model section 5).

Pure functions only: no I/O, no clock reads. "Today" is always passed in. Nothing else in the system may
implement this maths (constitution P2).
"""

import functools

from r2r_core.applies_if import parse_applies_if
from r2r_core.domain import LotType, RowFacts, StageKey
from r2r_core.profile import SiteProfile

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
