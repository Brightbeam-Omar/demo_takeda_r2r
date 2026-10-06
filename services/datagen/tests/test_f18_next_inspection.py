"""F18-FR-03g / OQ-100: next inspection dates in the plan and in the goods-receipt events."""

from datetime import timedelta

from datagen.events import plan_events
from datagen.model import Plan
from datagen.next_inspection import MANUFACTURE_LEAD, RETEST_DAYS


def test_f18_fr03g_every_drug_substance_batch_has_a_retest_date_and_consumables_none(plan: Plan) -> None:
    classes = {b.matnr: plan.world.material(b.matnr).klass for b in plan.batches}
    drug = [b for b in plan.batches if classes[b.matnr] == "drug_substance"]
    consumables = [b for b in plan.batches if classes[b.matnr] == "consumable"]
    assert drug and consumables
    assert all(b.next_inspection is not None for b in drug)
    assert all(b.next_inspection is None for b in consumables)


def test_f18_fr03g_retest_interval_is_12_to_36_months_after_manufacture(plan: Plan) -> None:
    for batch in plan.batches:
        if batch.next_inspection is None or batch.story_id is not None:
            continue
        gap = (batch.next_inspection - (batch.first_day - MANUFACTURE_LEAD)).days
        assert RETEST_DAYS[0] <= gap <= RETEST_DAYS[1]


def test_f18_fr03g_the_reeval_story_batch_keeps_its_story_cadence(plan: Plan) -> None:
    story = next(b for b in plan.batches if b.story_id == "B4410")
    assert story.next_inspection == story.lots[-1].start + timedelta(weeks=8)


def test_f18_fr03g_the_goods_receipt_event_carries_the_date(plan: Plan) -> None:
    receipts = [e for e in plan_events(plan) if e.kind == "goods_receipt"]
    by_batch = {(b.matnr, b.charg): b.next_inspection for b in plan.batches}
    assert receipts
    for event in receipts:
        assert event.body["qnext"] == by_batch[(event.body["matnr"], event.body["charg"])]


def test_f18_fr03g_non_reeval_story_batches_use_a_fixed_18_months(plan: Plan) -> None:
    from datagen.next_inspection import STORY_RETEST

    for batch in plan.batches:
        reeval = any(lot.lot_type == "09" for lot in batch.lots)
        if batch.story_id and not reeval and batch.next_inspection is not None:
            assert batch.next_inspection == batch.first_day - MANUFACTURE_LEAD + STORY_RETEST
