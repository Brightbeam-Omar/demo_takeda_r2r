"""Supplier batch numbers for the plan (the third line of the Overview material cell).

Every batch gets a generic supplier batch, ``SB-`` and six digits, so it never reads as the internal batch
number. Story batches are the same whatever the seed, so they draw nothing: their number follows from the
internal one. All draws use their own stream, so nothing planned before is reshuffled.
"""

import re

from datagen.model import Plan
from datagen.rng import stream

STREAM = "supplier_batches"
STORY_BASE = 900_000


def plan_supplier_batches(plan: Plan) -> None:
    """Set ``supplier_batch`` on every batch; the numbers are unique across the plan."""
    rng = stream(plan.seed, STREAM)
    used: set[str] = set()
    for batch in plan.batches:
        digits = re.sub(r"\D", "", batch.charg)
        if batch.story_id is not None and digits:
            batch.supplier_batch = f"SB-{STORY_BASE + int(digits)}"
            used.add(batch.supplier_batch)
    for batch in plan.batches:
        if batch.story_id is not None and batch.supplier_batch:
            continue
        while True:
            candidate = f"SB-{rng.randint(100_000, 899_999)}"
            if candidate not in used:
                break
        used.add(candidate)
        batch.supplier_batch = candidate
