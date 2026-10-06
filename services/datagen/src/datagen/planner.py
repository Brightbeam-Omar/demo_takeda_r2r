"""Builds the whole ``Plan`` for a site: the order of the phases is the order of the docstring below.

1. story batches (fixed)           2. re-evaluation chains (current lot, earlier lots, parent lot)
3. free released lots, topping up each week's usage decisions to its target
4. open lots by stage quota        5. materials and suppliers      6. batch numbers
7. need-by dates and demand lines, chosen so the RAG mix of open rows lands on target
"""

from collections import Counter
from datetime import date, timedelta
from decimal import Decimal

from r2r_core.domain import LotType, RowFacts, StageKey
from r2r_core.profile import SiteProfile
from r2r_core.sla import plan as plan_dates

from datagen.model import (
    BatchPlan,
    DemandPlan,
    LotPlan,
    Plan,
    current_stage_entry,
)
from datagen.next_inspection import plan_next_inspection
from datagen.params import Params
from datagen.po_lines import plan_po_lines
from datagen.quirks import apply_quirks
from datagen.stories import StoryResult, build_stories
from datagen.supplier_batches import plan_supplier_batches
from datagen.timeline import (
    OPEN_SAMPLED_STAGES,
    Builder,
    LotSpec,
    allocate,
    pick_weeks,
    weighted_choice,
)
from datagen.world import STORY_MATERIALS, World, build_world

FIRST_BATCH_NUMBER = 1001


def clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def build_plan(profile: SiteProfile, params: Params, seed: int, world: World | None = None) -> Plan:
    world = world or build_world(profile, params, seed)
    builder = Builder(profile, params, seed, world)
    plan = Plan(seed=seed, calendar=builder.calendar, world=world)
    story = _stories(builder, plan)
    _reeval_chains(builder, plan, story)
    released_free = _free_released(builder, plan)
    _open_lots(builder, plan, story, released_free)
    _assign_materials(builder, plan)
    _name_batches(plan, builder)
    for batch, lot in plan.lots():
        builder.verify(batch, lot)
    _need_by_and_demand(builder, plan, story)
    apply_quirks(plan, params, profile)
    plan_po_lines(plan, params)
    plan_next_inspection(plan)
    plan_supplier_batches(plan)
    return plan


# --- phase 1 --------------------------------------------------------------------------------------


def _stories(builder: Builder, plan: Plan) -> StoryResult:
    story = build_stories(builder)
    plan.batches.extend(story.batches)
    plan.deviations.extend(story.deviations)
    for batch in story.batches:
        for lot in batch.lots:
            builder.note_release(lot)
    return story


# --- phase 2 --------------------------------------------------------------------------------------


def _reeval_chains(builder: Builder, plan: Plan, story: StoryResult) -> None:
    params, rng, cal = builder.params, builder.rng, builder.calendar
    story_reeval = [b for b in story.batches if any(lot.lot_type == "09" for lot in b.lots)]
    story_open_current = sum(1 for b in story_reeval if b.lots[-1].stage != "released")
    generated = params.volumes.reeval_batches - len(story_reeval)
    open_current = (
        round(params.volumes.reeval_open_share * params.volumes.reeval_batches) - story_open_current
    )
    previous: list[int] = []
    for key, number in allocate(
        generated, {str(k): v for k, v in params.volumes.previous_reevals.items()}
    ).items():
        previous.extend([int(key)] * number)
    rng.shuffle(previous)
    mix = {stage: params.open_stage_mix[stage] for stage in OPEN_SAMPLED_STAGES}
    for index in range(generated):
        batch = builder.new_batch(False, onsite_only=True)
        if index < open_current:
            stage = weighted_choice(rng, mix)
            offsite = stage == "qc_ship" or (
                stage in ("qc_testing", "qa_release") and rng.random() < builder.provisional_offsite
            )
            spec = LotSpec("09", False, offsite, stage, builder.open_anchor(stage, "09"))
        else:
            week = pick_weeks(rng, cal.history_weeks, builder.weekly_target)
            spec = LotSpec(
                "09", False, rng.random() < builder.provisional_offsite, None, builder.release_day(week)
            )
        lots = [builder.build_lot(spec, "")]
        for _ in range(previous[index]):
            gap = timedelta(days=rng.randint(14, 45))
            earlier = LotSpec(
                "09",
                False,
                rng.random() < builder.provisional_offsite,
                None,
                cal.snap_back(lots[0].start - gap),
            )
            lots.insert(0, builder.build_lot(earlier, ""))
        parent_ud = cal.snap_back(lots[0].start - timedelta(days=rng.randint(14, 60)))
        lots.insert(
            0,
            builder.build_lot(
                LotSpec("01", False, rng.random() < builder.provisional_offsite, None, parent_ud), ""
            ),
        )
        batch.lots = lots
        for lot in lots:
            builder.note_release(lot)
        plan.batches.append(batch)


# --- phase 3 --------------------------------------------------------------------------------------


def _free_released(builder: Builder, plan: Plan) -> int:
    rng = builder.rng
    made = 0
    for week in builder.calendar.history_weeks:
        for _ in range(max(0, builder.weekly_target[week] - builder.released_in_week[week])):
            threepl = rng.random() < builder.provisional_threepl
            offsite = rng.random() < builder.provisional_offsite
            batch = builder.new_batch(threepl)
            lot = builder.build_lot(LotSpec("01", threepl, offsite, None, builder.release_day(week)), "")
            batch.lots = [lot]
            builder.note_release(lot)
            plan.batches.append(batch)
            made += 1
    return made


# --- phase 4 --------------------------------------------------------------------------------------


def _open_lots(builder: Builder, plan: Plan, story: StoryResult, released_free: int) -> None:
    params, rng = builder.params, builder.rng
    story_reeval = sum(1 for b in story.batches if any(lot.lot_type == "09" for lot in b.lots))
    reeval_generated = params.volumes.reeval_batches - story_reeval
    plain_open = params.volumes.batches - len(story.batches) - reeval_generated - released_free
    open_now = Counter(lot.stage for _, lot in plan.lots() if lot.stage != "released")
    open_total = plain_open + sum(open_now.values())
    wanted = allocate(open_total, params.open_stage_mix)
    counts = {stage: wanted[stage] - open_now.get(stage, 0) for stage in wanted}
    if any(n < 0 for n in counts.values()) or sum(counts.values()) != plain_open:
        raise ValueError(f"open stage quotas cannot be met: {counts} for {plain_open} plain open lots")
    # 3PL and offsite shares are corrected here, now the counts are known (the released lots used estimates)
    threepl_target = round(params.mix.threepl_share * params.volumes.batches)
    threepl_so_far = sum(1 for b in plan.batches if b.received_location_type == "3pl")
    others = plain_open - counts["pending"] - counts["call_off"]
    p_threepl = clamp(
        (threepl_target - threepl_so_far - counts["call_off"] - params.mix.threepl_share * counts["pending"])
        / max(1, others)
    )
    sampled_total = (
        sum(1 for _, lot in plan.lots() if lot.samples)
        + counts["qc_ship"]
        + counts["qc_testing"]
        + counts["qa_release"]
    )
    offsite_target = params.mix.offsite_share * sampled_total
    offsite_so_far = sum(1 for _, lot in plan.lots() if lot.latest and lot.latest.offsite) + counts["qc_ship"]
    p_offsite = clamp((offsite_target - offsite_so_far) / max(1, counts["qc_testing"] + counts["qa_release"]))
    order = [stage for stage, n in counts.items() for _ in range(n)]
    rng.shuffle(order)
    for stage in order:
        if stage == "pending":
            batch = builder.new_batch(rng.random() < params.mix.threepl_share)
            batch.lots = [builder.build_pending("")]
        else:
            threepl = stage == "call_off" or rng.random() < p_threepl
            offsite = stage == "qc_ship" or (
                stage in ("qc_testing", "qa_release") and rng.random() < p_offsite
            )
            batch = builder.new_batch(threepl)
            spec = LotSpec("01", threepl, offsite, stage, builder.open_anchor(stage, "01"))
            batch.lots = [builder.build_lot(spec, "")]
        plan.batches.append(batch)


# --- phases 5 and 6 --------------------------------------------------------------------------------


def _assign_materials(builder: Builder, plan: Plan) -> None:
    rng = builder.rng
    pool = [m for m in plan.world.materials if m.matnr not in STORY_MATERIALS]
    weights = [0.3 + rng.random() * 1.7 for _ in pool]
    for batch in plan.batches:
        if batch.matnr:
            continue
        material = rng.choices(pool, weights=weights)[0]
        batch.matnr = material.matnr
        batch.lifnr = material.suppliers[0] if rng.random() < 0.7 else rng.choice(material.suppliers)


def _name_batches(plan: Plan, builder: Builder) -> None:
    taken = {b.charg for b in plan.batches if b.charg}
    number = FIRST_BATCH_NUMBER
    unnamed = sorted(
        (b for b in plan.batches if not b.charg), key=lambda b: (b.first_day, b.matnr, b.quantity)
    )
    for batch in unnamed:
        while f"B{number}" in taken:
            number += 1
        batch.charg = f"B{number}"
        number += 1
    for batch in plan.batches:
        counters: Counter[str] = Counter()
        for lot in batch.lots:
            counters[lot.lot_type] += 1
            suffix = lot.lot_type if lot.lot_type == "01" else f"09-{counters['09']}"
            lot.ref = f"{batch.matnr}|{batch.charg}|{suffix}"
    plan.batches.sort(key=lambda b: (b.matnr, b.charg))


# --- phase 7: need-by dates, RAG, demand -----------------------------------------------------------


def facts_of(batch: BatchPlan, lot: LotPlan, need_by: date | None) -> RowFacts:
    latest = lot.latest
    return RowFacts(
        row_key=lot.ref,
        stage_key=StageKey(lot.stage),
        lot_type=LotType(lot.lot_type),
        received_location_type=batch.received_location_type,
        offsite=bool(latest and latest.offsite),
        current_stage_entry_date=current_stage_entry(batch, lot),
        system_need_by_locked=need_by,
        on_hold=False,
        ud_rejected=False,
        lims_status="none",
        ud_effective=False,
        ud_code=None,
        lims_approved_at=None,
    )


def rag_of(
    profile: SiteProfile, batch: BatchPlan, lot: LotPlan, need_by: date | None, today: date
) -> str | None:
    result = plan_dates(facts_of(batch, lot, need_by), profile, today)
    return None if result.rag is None else str(result.rag)


def _need_by_and_demand(builder: Builder, plan: Plan, story: StoryResult) -> None:
    params, rng, cal, profile = builder.params, builder.rng, builder.calendar, builder.profile
    by_material: dict[str, list[tuple[BatchPlan, LotPlan]]] = {}
    for batch, lot in plan.lots():
        if lot.stage not in ("released", "pending"):
            by_material.setdefault(batch.matnr, []).append((batch, lot))
    ragged = sum(len(v) for v in by_material.values())
    quota = allocate(ragged, params.rag_mix)
    seen: Counter[str] = Counter()

    def classes(matnr: str, need_by: date | None) -> list[str | None]:
        return [rag_of(profile, b, lot, need_by, cal.today) for b, lot in by_material[matnr]]

    chosen: dict[str, date | None] = {}
    campaigns: dict[str, str] = {}
    for matnr, (campaign, day) in story.need_by.items():
        chosen[matnr], campaigns[matnr] = day, campaign
        seen.update(c for c in classes(matnr, day) if c)
    free = [m for m in sorted(by_material) if m not in chosen]
    rng.shuffle(free)
    none_count = round(params.demand.no_demand_share * len(by_material))
    for matnr in free[:none_count]:
        chosen[matnr] = None
        seen.update(c for c in classes(matnr, None) if c)
    candidates = list(range(0, params.demand.need_by_max_days + 1))
    for matnr in free[none_count:]:
        remaining = {c: max(0, quota[c] - seen[c]) + 0.05 for c in quota}
        target = weighted_choice(rng, remaining)
        best: tuple[int, date, list[str | None]] | None = None
        for days in rng.sample(candidates, 80):
            day = cal.today + timedelta(days=days)
            found = classes(matnr, day)
            score = sum(1 for c in found if c == target)
            if best is None or score > best[0]:
                best = (score, day, found)
            if score == len(found):
                break
        assert best is not None
        chosen[matnr] = best[1]
        seen.update(c for c in best[2] if c)
    plan.need_by = chosen
    _demand_lines(builder, plan, chosen, campaigns)


def _demand_lines(
    builder: Builder, plan: Plan, chosen: dict[str, date | None], campaigns: dict[str, str]
) -> None:
    params, rng, cal = builder.params, builder.rng, builder.calendar
    first_use: dict[str, date] = {}
    for batch in plan.batches:
        first_use[batch.matnr] = min(first_use.get(batch.matnr, batch.first_day), batch.first_day)
    window_start = cal.today - timedelta(days=7 * cal.weeks)

    def quantity() -> Decimal:
        return Decimal(rng.choice(params.quirks.quantities)) * rng.choice([1, 2, 3])

    def created_before(day: date, matnr: str) -> date:
        anchor = min(first_use.get(matnr, day), day, cal.last_day)
        return cal.snap_back(
            max(anchor - timedelta(days=rng.randint(7, 45)), window_start - timedelta(days=90))
        )

    for material in plan.world.materials:
        matnr = material.matnr
        primary = chosen.get(matnr)
        has_open_lots = matnr in chosen
        if not has_open_lots and rng.random() < 0.5:
            primary = cal.today + timedelta(days=rng.randint(10, params.demand.need_by_max_days))
        campaign = campaigns.get(matnr) or rng.choice(plan.world.campaigns)
        if primary is not None:
            plan.demands.append(
                DemandPlan(matnr, campaign, primary, quantity(), created_before(primary, matnr))
            )
            extra = int(weighted_choice(rng, {str(k): v for k, v in params.demand.extra_rows.items()}))
            for _ in range(extra):
                later = primary + timedelta(days=rng.randint(14, 120))
                other = rng.choice([c for c in plan.world.campaigns if c != campaign])
                plan.demands.append(
                    DemandPlan(matnr, other, later, quantity(), created_before(primary, matnr))
                )
        if rng.random() < params.demand.closed_history_share:
            required = cal.snap_back(cal.today - timedelta(days=rng.randint(10, 120)))
            created = cal.snap_back(required - timedelta(days=rng.randint(20, 60)))
            closed = min(cal.last_day, required + timedelta(days=rng.randint(0, 10)))
            plan.demands.append(
                DemandPlan(
                    matnr,
                    rng.choice(plan.world.campaigns),
                    required,
                    quantity(),
                    created,
                    closed_on=cal.snap_back(closed),
                )
            )
        if rng.random() < params.demand.stale_open_share:
            required = cal.snap_back(cal.today - timedelta(days=rng.randint(5, 60)))
            created = cal.snap_back(required - timedelta(days=rng.randint(20, 60)))
            plan.demands.append(
                DemandPlan(matnr, rng.choice(plan.world.campaigns), required, quantity(), created)
            )
