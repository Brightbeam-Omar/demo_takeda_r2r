"""History behind the Reports & Metrics figures (F20-FR-07): needs-by adherence and expedites.

Both are new plans on their own rng streams, added after everything else is planned, so no stage, date, SLA
input or count of an existing lot moves (the F05 report counts and the week-41 percentages stay as they are).

**Needs-by adherence.** The pipeline gives a released lot the earliest demand line of its material dated on or
after the lot's cycle start, closed lines included (04 section 3). The plan reproduces that rule on its own
demand lines, then adds *closed* lines (they never touch an open lot's need-by) until the share of late lots
lands on target:

1. a released lot that would have no need-by gets a line a few days after its release (on time);
2. lots are then flipped to late, one at a time, by a line just before their release, until the target
   share of late lots is reached (a line only ever makes lots of its own material later).

**Expedites.** A few released single-lot batches get an ERP expedite request: all but one released by their
due date.
"""

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from datagen.model import ACCEPT_CODES, Calendar, DemandPlan, ExpeditePlan, LotPlan, Plan
from datagen.params import Params
from datagen.rng import stream

ADHERENCE_STREAM = "f20_adherence"
EXPEDITE_STREAM = "f20_expedites"
EXPEDITE_MIN_CYCLE_DAYS = (
    10  # the request is made 2 days into the cycle and a missed due date is 3+ days early
)


def released_lots(plan: Plan) -> list[tuple[str, LotPlan]]:
    """``(material, lot)`` of every lot with an effective usage decision, in release order."""
    found = [
        (batch.matnr, lot)
        for batch, lot in plan.lots()
        if lot.ud_code in ACCEPT_CODES and lot.ud_date is not None and not lot.reversed_same_day
    ]
    return sorted(found, key=lambda item: (item[1].ud_date or plan.calendar.today, item[1].ref))


def need_by_at_release(lot: LotPlan, lines: list[DemandPlan]) -> date | None:
    """The pipeline rule: earliest requirement date on or after the lot's cycle start, closed lines too."""
    return min((d.requirement_date for d in lines if d.requirement_date >= lot.start), default=None)


def adherence(plan: Plan) -> tuple[int, int, int]:
    """``(on time, late, without a need-by)`` of the released lots, by the pipeline rule."""
    lines = _lines_by_material(plan)
    on_time = late = none = 0
    for matnr, lot in released_lots(plan):
        need_by = need_by_at_release(lot, lines[matnr])
        if need_by is None:
            none += 1
        elif lot.ud_date is not None and lot.ud_date <= need_by:
            on_time += 1
        else:
            late += 1
    return on_time, late, none


def _lines_by_material(plan: Plan) -> dict[str, list[DemandPlan]]:
    grouped: dict[str, list[DemandPlan]] = defaultdict(list)
    for demand in plan.demands:
        grouped[demand.matnr].append(demand)
    return grouped


def plan_report_facts(plan: Plan, params: Params) -> None:
    _plan_adherence(plan, params)
    _plan_expedites(plan, params)


def _closed_line(matnr: str, campaign: str, lot: LotPlan, required: date, created_gap: int) -> DemandPlan:
    """A demand line that was created before the lot started and closed when it was released."""
    return DemandPlan(
        matnr=matnr,
        campaign=campaign,
        requirement_date=required,
        quantity=Decimal(100),
        created_on=Calendar.snap_back(lot.start - timedelta(days=created_gap)),
        closed_on=lot.ud_date,
    )


def _plan_adherence(plan: Plan, params: Params) -> None:
    cfg = params.report_facts
    rng = stream(plan.seed, ADHERENCE_STREAM)
    lines = _lines_by_material(plan)
    lots = released_lots(plan)

    def add(matnr: str, lot: LotPlan, required: date) -> None:
        line = _closed_line(matnr, rng.choice(plan.world.campaigns), lot, required, rng.randint(1, 10))
        plan.demands.append(line)
        lines[matnr].append(line)

    # 1. every released lot gets a need-by, met by default
    for matnr, lot in lots:
        if need_by_at_release(lot, lines[matnr]) is None:
            assert lot.ud_date is not None
            add(matnr, lot, lot.ud_date + timedelta(days=rng.randint(*cfg.anchor_days)))

    def is_late(matnr: str, lot: LotPlan) -> bool:
        need_by = need_by_at_release(lot, lines[matnr])
        return need_by is not None and lot.ud_date is not None and lot.ud_date > need_by

    # 2. flip lots to late until the target share is reached
    target = round(cfg.late_share * len(lots))
    late = sum(1 for matnr, lot in lots if is_late(matnr, lot))
    candidates = [item for item in lots if not is_late(*item) and _has_a_day_before_release(item[1])]
    rng.shuffle(candidates)
    for matnr, lot in candidates:
        if late >= target:
            break
        if is_late(matnr, lot):  # an earlier flip of the same material already made it late
            continue
        assert lot.ud_date is not None
        earliest = max(lot.start, lot.ud_date - timedelta(days=cfg.late_lead_days))
        span = (lot.ud_date - earliest).days  # at least 1: the lot started before its release
        add(matnr, lot, earliest + timedelta(days=rng.randint(0, span - 1)))
        late = sum(1 for m, other in lots if is_late(m, other))


def _has_a_day_before_release(lot: LotPlan) -> bool:
    return lot.ud_date is not None and lot.ud_date > lot.start


def _plan_expedites(plan: Plan, params: Params) -> None:
    cfg = params.report_facts
    rng = stream(plan.seed, EXPEDITE_STREAM)
    window_start = plan.calendar.today - timedelta(weeks=20)
    candidates = [
        (batch, lot)
        for batch, lot in plan.lots()
        if len(batch.lots) == 1
        and batch.story_id is None
        and lot.ud_code in ACCEPT_CODES
        and lot.ud_date is not None
        and lot.ud_date >= window_start
        and (lot.ud_date - lot.start).days >= EXPEDITE_MIN_CYCLE_DAYS
    ]
    candidates.sort(key=lambda item: item[1].ref)
    chosen = rng.sample(candidates, cfg.expedites)
    for index, (batch, lot) in enumerate(chosen):
        assert lot.ud_date is not None
        requested = Calendar.snap_back(lot.start + timedelta(days=2))
        if index < cfg.expedites_missed:
            due = lot.ud_date - timedelta(days=rng.randint(3, 5))  # released after the due date
        else:
            due = lot.ud_date + timedelta(days=rng.randint(0, 5))  # on or before it
        plan.expedites.append(ExpeditePlan(batch.matnr, batch.charg, requested, due))
