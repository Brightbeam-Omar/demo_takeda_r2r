"""The five story batches (F05-FR-06). Filled in by task T5."""

from dataclasses import dataclass, field
from datetime import date

from datagen.model import BatchPlan, DeviationPlan


@dataclass
class StoryResult:
    batches: list[BatchPlan] = field(default_factory=list)
    need_by: dict[str, tuple[str, date]] = field(default_factory=dict)  # matnr -> (campaign, need-by date)
    deviations: list[DeviationPlan] = field(default_factory=list)


def build_stories(builder: object) -> StoryResult:
    return StoryResult()
