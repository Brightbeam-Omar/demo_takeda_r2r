"""The supplier batch of every plan batch is generic, unique and not the internal batch number."""

import re

from datagen.events import plan_events
from datagen.model import Plan
from datagen.params import Params
from datagen.planner import build_plan
from r2r_core.profile import SiteProfile


def test_f18_every_batch_has_a_generic_supplier_batch_that_is_not_its_batch_number(plan: Plan) -> None:
    numbers = [b.supplier_batch for b in plan.batches]
    assert all(n is not None and re.fullmatch(r"SB-\d{6}", n) for n in numbers)
    assert len(set(numbers)) == len(numbers)
    assert all(b.supplier_batch != b.charg for b in plan.batches)


def test_f18_story_supplier_batches_are_the_same_whatever_the_seed(
    profile: SiteProfile, params: Params, plan: Plan
) -> None:
    other = build_plan(profile, params, 7)
    stories = lambda p: {b.charg: b.supplier_batch for b in p.batches if b.story_id}  # noqa: E731
    assert stories(other) == stories(plan)
    assert stories(plan)["B2077"] == "SB-902077"


def test_f18_the_goods_receipt_event_carries_the_supplier_batch(plan: Plan) -> None:
    by_batch = {(b.matnr, b.charg): b.supplier_batch for b in plan.batches}
    receipts = [e for e in plan_events(plan) if e.kind == "goods_receipt"]
    assert receipts
    assert all(e.body["licha"] == by_batch[(e.body["matnr"], e.body["charg"])] for e in receipts)
