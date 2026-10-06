"""Purchase-order lines for the plan (F17-FR-02).

Every delivery gets a line created 2-8 weeks before its receipt (the receipt closes it, and a same-day
reversal reopens it). On top of those, lines for deliveries that have not arrived yet bring the open total at
demo start to the configured range. All draws use their own stream, so nothing planned before is reshuffled.
"""

from datetime import timedelta
from decimal import Decimal

from datagen.model import Calendar, Plan, PoLinePlan
from datagen.params import Params
from datagen.rng import stream

STREAM = "po_lines"
ONSITE_SHARE = 0.7  # of the lines still to arrive, the share planned into an onsite location


def plan_po_lines(plan: Plan, params: Params) -> None:
    """Fill ``plan.po_lines`` and set ``po_ref`` on every batch."""
    cfg, rng, calendar = params.po_lines, stream(plan.seed, STREAM), plan.calendar
    for batch in plan.batches:
        receipt = batch.first_day
        lead = rng.randint(*cfg.lead_days)
        jitter = rng.randint(*cfg.receipt_jitter_days)
        batch.po_ref = f"{batch.matnr}|{batch.charg}"
        plan.po_lines.append(
            PoLinePlan(
                ref=batch.po_ref,
                matnr=batch.matnr,
                lifnr=batch.lifnr,
                lgort=batch.lgort,
                quantity=batch.quantity,
                scheduled=receipt + timedelta(days=jitter),
                created_on=Calendar.snap_back(receipt - timedelta(days=lead)),
            )
        )
    reopened = sum(1 for _, lot in plan.lots() if lot.reversed_same_day)
    total = rng.randint(*cfg.open_total)
    overdue_wanted = max(0, round(cfg.overdue_share * total) - reopened)
    today = calendar.today
    for number in range(max(0, total - reopened)):
        material = rng.choice(plan.world.materials)
        supplier = rng.choice(material.suppliers)
        places = plan.world.onsite if rng.random() < ONSITE_SHARE else plan.world.threepl
        if number < overdue_wanted:
            scheduled = Calendar.snap_back(today - timedelta(days=rng.randint(1, cfg.overdue_max_days)))
        else:
            scheduled = today + timedelta(days=rng.randint(0, cfg.due_within_days))
        lead = rng.randint(*cfg.lead_days)
        plan.po_lines.append(
            PoLinePlan(
                ref=f"open-{number + 1}",
                matnr=material.matnr,
                lifnr=supplier,
                lgort=rng.choice(places).lgort,
                quantity=Decimal(rng.choice(params.quirks.quantities)),
                scheduled=scheduled,
                created_on=min(Calendar.snap_back(scheduled - timedelta(days=lead)), calendar.last_day),
                open_at_start=True,
            )
        )
