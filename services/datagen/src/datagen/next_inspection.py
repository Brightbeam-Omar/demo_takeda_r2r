"""Next inspection (retest) dates for the plan (F18-FR-03g, OQ-100).

Every drug-substance batch, in flight or released, gets its manufacturing date plus a retest interval of
12 to 36 months. Story batches draw nothing (they are the same whatever the seed): a fixed 18 months, and
for the re-evaluation story its own cadence, one story interval after the open re-evaluation lot started.
Consumables have none. All draws use their own stream, so nothing planned before is reshuffled.
"""

from datetime import timedelta

from datagen.model import Plan
from datagen.rng import stream

STREAM = "next_inspection"
RETEST_DAYS = (365, 1095)  # 12 to 36 months
REEVAL_STORY_INTERVAL = timedelta(weeks=8)  # the cadence of the earlier re-evaluation lots in the story
STORY_RETEST = timedelta(days=548)  # 18 months: story batches use a fixed interval
MANUFACTURE_LEAD = timedelta(days=21)  # events.py posts the manufacture date this long before the receipt


def plan_next_inspection(plan: Plan) -> None:
    """Set ``next_inspection`` on every drug-substance batch."""
    rng = stream(plan.seed, STREAM)
    for batch in plan.batches:
        if plan.world.material(batch.matnr).klass != "drug_substance":
            continue
        manufactured = batch.first_day - MANUFACTURE_LEAD
        if batch.story_id is not None:  # stories are the same whatever the seed, so they draw nothing
            reeval = any(lot.lot_type == "09" for lot in batch.lots)
            batch.next_inspection = (
                batch.lots[-1].start + REEVAL_STORY_INTERVAL if reeval else manufactured + STORY_RETEST
            )
            continue
        batch.next_inspection = manufactured + timedelta(days=rng.randint(*RETEST_DAYS))
