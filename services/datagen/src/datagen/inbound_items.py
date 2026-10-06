"""Inbound sub-checks and resolved checks for the plan (F19-FR-02, OQ-107).

About 8% of the passed checks of ordinary lots become ``resolved`` (completed with an issue resolved; it
behaves like ``passed`` in the stage engine, so no intended stage changes). Every lot that has a check gets
5 to 9 sub-checks: the first N of a fixed list of nine generic labels, each with its default outcome. A failed
or resolved check has at least one FAIL; an open check has PENDING on its last items. Story batches draw
nothing (they are the same whatever the seed): all nine items, none failing. Both draws use their own
streams, so nothing planned before is reshuffled.
"""

import random

from datagen.model import LotPlan, Plan
from datagen.rng import stream

RESOLVED_STREAM = "inbound_resolved"
ITEMS_STREAM = "inbound_items"
RESOLVED_SHARE = 0.08
ITEM_COUNT = (5, 9)

# (check_code, check_label, outcome of a passed check). The first five are the ones that can fail.
ITEM_LIST: tuple[tuple[str, str, str], ...] = (
    ("PHYS", "Physical evaluation", "PASS"),
    ("INBD", "Inbound delivery check", "PASS"),
    ("SUPB", "Supplier batch verification", "PASS"),
    ("QTYR", "Quantity received verification", "PASS"),
    ("DATE", "Date verification (expiry/mfg/re-eval/COA)", "PASS"),
    ("COAC", "Certificate of analysis", "APRV"),
    ("DEVB", "Deviation on batch", "NO"),
    ("BUSE", "Batch use", "DCPS"),
    ("RESL", "Results of analytical work", "COMP"),
)
FAILABLE = 5


def _items(lot: LotPlan, count: int, rng: random.Random | None) -> list[tuple[str, str, str]]:
    items = list(ITEM_LIST[:count])
    if lot.check in ("failed", "resolved") and rng is not None:
        failing = rng.sample(range(FAILABLE), 2 if lot.check == "failed" and rng.random() < 0.4 else 1)
        for index in failing:
            code, label, _ = items[index]
            items[index] = (code, label, "FAIL")
    if lot.check == "open" and rng is not None:
        pending = min(count, rng.randint(1, 3))
        for index in range(count - pending, count):
            code, label, _ = items[index]
            items[index] = (code, label, "PENDING")
    return items


def plan_inbound_items(plan: Plan) -> None:
    """Turn some passed checks into resolved ones, then give every check its sub-checks."""
    resolved_rng = stream(plan.seed, RESOLVED_STREAM)
    for _, lot in plan.lots():
        if lot.check == "passed" and not lot.story_id and resolved_rng.random() < RESOLVED_SHARE:
            lot.check = "resolved"
            lot.tags.append("resolved_check")
    items_rng = stream(plan.seed, ITEMS_STREAM)
    for _, lot in plan.lots():
        if lot.check == "none" or lot.reversed_same_day:
            continue
        if lot.story_id:
            lot.check_items = _items(lot, ITEM_COUNT[1], None)
        else:
            lot.check_items = _items(lot, items_rng.randint(*ITEM_COUNT), items_rng)
