"""Realism quirks and deviations (F05-FR-05, F05-AC-03).

Each injector picks lots from a seeded stream and edits the plan without changing any intended stage. A lot's
stage is checked again afterwards by ``derive_stage``. ``quirk_counts`` is what the report and the tests use
to see that every quirk is present at least three times.
"""

import random
from datetime import UTC, datetime, time, timedelta

from r2r_core.airgap import air_gap
from r2r_core.profile import SiteProfile

from datagen.model import (
    BatchPlan,
    DeviationPlan,
    LotPlan,
    Plan,
    SamplePlan,
    sampling_entry,
    weekdays_between,
)
from datagen.params import Params
from datagen.rng import stream

QUIRKS = (
    "gr_reversal_same_day",
    "batch_without_demand",
    "consumable_in_testing",
    "erp_blocked_stock",
    "on_hold_batch",
    "rejected_ud",
    "air_gap",
    "open_deviation_in_qa_release",
    "failed_inbound_check",
    "concurrent_batches_two_campaigns",
)

TITLES = (
    "Temperature excursion in storage",
    "Damaged outer packaging on receipt",
    "Label does not match the order",
    "Certificate of analysis missing",
    "Sample container leaked",
    "Out-of-trend result in testing",
    "Shipping documents incomplete",
    "Pallet seal found broken",
    "Delivery received outside the agreed window",
    "Quantity differs from the delivery note",
)
ROOT_CAUSES = (
    "Transport",
    "Supplier documentation",
    "Storage conditions",
    "Handling",
    "Equipment",
    "Method",
)
OPEN_CAUSE = "Not yet determined"
OWNERS = ("QA", "QA", "Warehouse", "QC Lab")


def apply_quirks(plan: Plan, params: Params, profile: SiteProfile) -> None:
    rng = stream(plan.seed, "quirks")
    used: set[int] = set()
    _failed_checks(plan, params, rng, used)
    _rejected_uds(plan, params, rng, used)
    _holds_and_blocks(plan, params, rng, used)
    _lims_retests(plan, rng, used)
    _results_recorded(plan, params, rng, profile)
    _deviations(plan, params, rng)


def _in_flight(plan: Plan) -> list[tuple[BatchPlan, LotPlan]]:
    return [
        (b, lot) for b, lot in plan.lots() if lot.stage not in ("released", "pending") and not lot.story_id
    ]


def _failed_checks(plan: Plan, params: Params, rng: random.Random, used: set[int]) -> None:
    cal = plan.calendar
    pool = [
        (b, lot)
        for b, lot in _in_flight(plan)
        if lot.stage == "receipt"
        and lot.check == "open"
        and weekdays_between(lot.start + timedelta(days=1), cal.last_day)
    ]
    for _, lot in rng.sample(pool, min(params.quirks.failed_inbound_checks, len(pool))):
        lot.check = "failed"
        lot.check_done = rng.choice(weekdays_between(lot.start + timedelta(days=1), cal.last_day))
        lot.tags.append("failed_check")


def _rejected_uds(plan: Plan, params: Params, rng: random.Random, used: set[int]) -> None:
    cal = plan.calendar
    pool = [
        (b, lot)
        for b, lot in _in_flight(plan)
        if lot.stage == "qa_release"
        and lot.lot_type == "01"
        and lot.latest is not None
        and lot.latest.closed_on is not None
        and weekdays_between(lot.latest.closed_on + timedelta(days=1), cal.last_day)
    ]
    for batch, lot in rng.sample(pool, min(params.quirks.rejected_uds, len(pool))):
        assert lot.latest is not None and lot.latest.closed_on is not None
        window = weekdays_between(lot.latest.closed_on + timedelta(days=1), cal.last_day)[:3]
        lot.ud_code, lot.ud_date = "R", rng.choice(window)
        lot.tags.append("rejected_ud")
        used.add(id(batch))


def _holds_and_blocks(plan: Plan, params: Params, rng: random.Random, used: set[int]) -> None:
    cal = plan.calendar
    open_batches = [b for b, _ in _in_flight(plan) if id(b) not in used]
    open_batches = list({id(b): b for b in open_batches}.values())

    def pick(count: int, pool: list[BatchPlan]) -> list[BatchPlan]:
        chosen = rng.sample(pool, min(count, len(pool)))
        used.update(id(b) for b in chosen)
        return chosen

    for batch in pick(params.quirks.on_hold_batches, [b for b in open_batches if b.first_day < cal.last_day]):
        batch.holds.append(
            (rng.choice(weekdays_between(batch.first_day + timedelta(days=1), cal.last_day)), True)
        )
    fresh = [
        b
        for b in plan.batches
        if id(b) not in used and not b.story_id and b.first_day < cal.last_day - timedelta(days=4)
    ]
    for batch in pick(params.quirks.released_holds, fresh):
        days = weekdays_between(batch.first_day + timedelta(days=1), cal.last_day)
        first, second = sorted(rng.sample(days, 2))
        batch.holds.extend([(first, True), (second, False)])
    blockable = [
        b
        for b in open_batches
        if id(b) not in used
        and len(b.lots) == 1
        and b.lots[0].lot_type == "01"
        and b.lots[0].stage in ("sampling", "qc_ship", "qc_testing", "qa_release")
        and b.lots[0].ud_code is None
        and (b.lots[0].transfer or b.lots[0].start) < cal.last_day
    ]
    for batch in pick(params.quirks.erp_blocked_batches, blockable):
        lot = batch.lots[0]
        batch.blocks.append((rng.choice(weekdays_between(lot.transfer or lot.start, cal.last_day)), True))
        lot.tags.append("erp_blocked")


def _lims_retests(plan: Plan, rng: random.Random, used: set[int]) -> None:
    cal = plan.calendar
    rejected_now = [
        lot
        for b, lot in _in_flight(plan)
        if lot.stage == "qc_testing"
        and lot.latest is not None
        and not lot.latest.offsite
        and lot.latest.outcome == "open"
        and weekdays_between(lot.latest.collected + timedelta(days=1), cal.last_day)
    ]
    for lot in rng.sample(rejected_now, min(5, len(rejected_now))):
        assert lot.latest is not None
        lot.latest.outcome = "rejected"
        lot.latest.closed_on = rng.choice(
            weekdays_between(lot.latest.collected + timedelta(days=1), cal.last_day)
        )
        lot.tags.append("lims_rejected")
    retestable = []
    for batch, lot in plan.lots():
        entry = sampling_entry(batch, lot)
        sample = lot.latest
        if (
            lot.story_id is None
            and not lot.tags
            and sample is not None
            and not sample.offsite
            and sample.outcome in ("open", "approved")
            and entry is not None
            and (sample.collected - entry).days >= 4
        ):
            retestable.append((entry, lot))
    for entry, lot in rng.sample(retestable, min(6, len(retestable))):
        assert lot.latest is not None
        first = rng.choice(
            weekdays_between(entry + timedelta(days=1), lot.latest.collected - timedelta(days=1))
        )
        earlier = SamplePlan(
            collected=first, started=first, outcome="rejected", closed_on=lot.latest.collected
        )
        lot.samples.insert(0, earlier)
        lot.tags.append("lims_retest")


def _results_recorded(plan: Plan, params: Params, rng: random.Random, profile: SiteProfile) -> None:
    """The interface records a lot's LIMS results in the ERP 1-6 hours after approval, except air gaps.

    The air-gap quirk withholds the transfer on a few lots; B5003, fixed by the story at 30 hours, is one of
    them. The others are approved at `air_gap_ages_hours` before the opening instant (for example 62, 70 and
    90 hours; the opening is a Monday, so ages of 32 to 55 hours would fall on a weekend), so the air-gap list
    shows a spread of ages inside the 24 to 96 hour band. A lot is eligible for a target age when it was
    already approved on the site-local day of that instant. No other approved lot lacks the record.
    """
    cal = plan.calendar
    opening = profile.demo.start_datetime.astimezone(UTC)
    pool = [
        lot
        for b, lot in _in_flight(plan)
        if lot.stage == "qa_release"
        and lot.ud_code is None
        and lot.latest is not None
        and lot.latest.closed_on is not None
        and 2 <= (cal.today - lot.latest.closed_on).days <= 5
    ]
    fixed = sum(1 for _, lot in plan.lots() if "air_gap" in lot.tags)
    ages = params.quirks.air_gap_ages_hours[: max(0, params.quirks.air_gap_lots - fixed)]
    for hours in ages:
        approved = opening - timedelta(hours=hours)
        day = approved.astimezone(profile.site.tz).date()
        candidates = [lot for lot in pool if lot.latest is not None and lot.latest.closed_on == day]
        lot = rng.choice(candidates)
        pool.remove(lot)
        assert lot.latest is not None
        lot.latest.approved_at = approved
        lot.tags.append("air_gap")
    for _, lot in plan.lots():
        sample = lot.latest
        if (
            sample is None
            or sample.outcome != "approved"
            or sample.closed_on is None
            or "air_gap" in lot.tags
        ):
            continue
        base = datetime.combine(sample.closed_on, time(6), tzinfo=UTC)
        delay = (
            timedelta(hours=3)
            if lot.story_id
            else timedelta(hours=rng.randint(1, 6), minutes=rng.randint(0, 59))
        )
        lot.results_recorded = base + delay


def _deviations(plan: Plan, params: Params, rng: random.Random) -> None:
    cal = plan.calendar
    lots_by_batch = {(b.matnr, b.charg): b.lots for b in plan.batches}
    stage_of = {key: [lot.stage for lot in lots] for key, lots in lots_by_batch.items()}
    story = list(plan.deviations)
    open_total = round(params.volumes.deviation_open_share * params.volumes.deviations)
    open_story = sum(1 for d in story if d.closed_on is None)
    story_qa = sum(
        1 for d in story if d.closed_on is None and any("qa_release" in stage_of[link] for link in d.links)
    )
    in_qa = [b for b, lot in _in_flight(plan) if lot.stage == "qa_release"]
    in_qa = list({id(b): b for b in in_qa}.values())
    other_open = [b for b, _ in _in_flight(plan) if "qa_release" not in [lot.stage for lot in b.lots]]
    other_open = list({id(b): b for b in other_open}.values())
    anywhere = [b for b in plan.batches if b.first_day < cal.last_day - timedelta(days=4)]
    severities = list(params.deviations.severity)
    severity_weights = list(params.deviations.severity.values())

    def build(batch: BatchPlan, is_open: bool) -> DeviationPlan | None:
        links = [(batch.matnr, batch.charg)]
        if rng.random() < params.deviations.links[2]:
            partner = rng.choice(anywhere)
            if partner is not batch and partner.first_day < cal.last_day - timedelta(days=2):
                links.append((partner.matnr, partner.charg))
        floor = max(b.first_day for b in plan.batches if (b.matnr, b.charg) in links) + timedelta(days=1)
        ceiling = cal.last_day if is_open else cal.last_day - timedelta(days=2)
        days = weekdays_between(floor, ceiling)
        if not days:
            return None
        opened = rng.choice(days)
        closed = None
        if not is_open:
            later = weekdays_between(
                opened + timedelta(days=1), min(cal.last_day, opened + timedelta(days=40))
            )
            if not later:
                return None
            closed = rng.choice(later)
        title = rng.choice(TITLES)
        status = "being assessed" if is_open else "assessed and closed"
        return DeviationPlan(
            title=title,
            description=f"{title}. Recorded at site; impact on the batch is {status}.",
            severity=rng.choices(severities, weights=severity_weights)[0],
            opened_on=opened,
            closed_on=closed,
            root_cause_category=OPEN_CAUSE if is_open else rng.choice(ROOT_CAUSES),
            owner=rng.choice(OWNERS),
            links=links,
        )

    def add(count: int, pool: list[BatchPlan], is_open: bool) -> None:
        added, tries = 0, 0
        while added < count and tries < 20 * max(1, count):
            tries += 1
            deviation = build(rng.choice(pool), is_open)
            if deviation is not None:
                plan.deviations.append(deviation)
                added += 1

    open_qa = max(0, params.deviations.open_on_qa_release - story_qa)
    add(open_qa, in_qa, True)
    add(max(0, open_total - open_story - open_qa), other_open, True)
    add(params.volumes.deviations - len(plan.deviations), anywhere, False)


def quirk_counts(plan: Plan, profile: SiteProfile) -> dict[str, int]:
    """How often each quirk occurs in the plan (a batch, lot or material counts once)."""
    cal = plan.calendar
    now = profile.demo.start_datetime.astimezone(UTC)
    threshold = profile.air_gap.threshold_hours
    lots = plan.lots()
    klass = {m.matnr: m.klass for m in plan.world.materials}
    open_demand = [d for d in plan.demands if d.closed_on is None and d.requirement_date >= cal.today]
    demand_campaigns: dict[str, set[str]] = {}
    for demand in open_demand:
        demand_campaigns.setdefault(demand.matnr, set()).add(demand.campaign)
    in_flight_batches: dict[str, set[str]] = {}
    for batch, lot in lots:
        if lot.stage not in ("released", "pending"):
            in_flight_batches.setdefault(batch.matnr, set()).add(batch.charg)
    qa_batches = {(b.matnr, b.charg) for b, lot in lots if lot.stage == "qa_release"}

    def approved_at(lot: LotPlan) -> datetime | None:
        sample = lot.latest
        if sample is None or sample.outcome != "approved" or sample.closed_on is None:
            return None
        return sample.approved_at or datetime.combine(sample.closed_on, time(6), tzinfo=UTC)

    def blocked(batch: BatchPlan) -> bool:
        net = batch.blocks[-1][1] if batch.blocks else False
        return net or any(lot.ud_code == "R" for lot in batch.lots)

    return {
        "gr_reversal_same_day": sum(1 for _, lot in lots if lot.reversed_same_day),
        "batch_without_demand": sum(
            1
            for b in plan.batches
            if b.matnr not in demand_campaigns
            and any(lot.stage not in ("released", "pending") for lot in b.lots)
        ),
        "consumable_in_testing": sum(
            1 for b, lot in lots if lot.stage == "qc_testing" and klass[b.matnr] == "consumable"
        ),
        "erp_blocked_stock": sum(1 for b in plan.batches if blocked(b)),
        "on_hold_batch": sum(1 for b in plan.batches if b.holds and b.holds[-1][1]),
        "rejected_ud": sum(1 for _, lot in lots if lot.ud_code == "R"),
        "air_gap": sum(
            1
            for _, lot in lots
            if (when := approved_at(lot)) is not None
            and air_gap("approved", lot.ud_code, when, now, threshold, lot.results_recorded)[0]
        ),
        "open_deviation_in_qa_release": sum(
            1 for d in plan.deviations if d.closed_on is None and any(link in qa_batches for link in d.links)
        ),
        "failed_inbound_check": sum(1 for _, lot in lots if lot.check == "failed"),
        "concurrent_batches_two_campaigns": sum(
            1
            for matnr, batches in in_flight_batches.items()
            if len(batches) >= 2 and len(demand_campaigns.get(matnr, set())) >= 2
        ),
    }
