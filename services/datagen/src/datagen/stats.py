"""Numbers about a plan: volumes, the open-row stage mix, the RAG mix and the weekly metric completions.

The stage mix is computed from the generator's *intended* stage labels (F05-FR-11), the RAG mix with the
shared SLA library and the weekly metrics with the definitions of 03-domain-model section 7. The report
prints these and the tests assert on them.
"""

from collections import Counter
from dataclasses import dataclass, field
from datetime import date

from r2r_core.profile import SiteProfile
from r2r_core.sla import sla_for

from datagen.model import Plan, stage_dates
from datagen.planner import rag_of

METRICS = {"M3": "sampling", "M6": "qc_testing", "M7": "qa_release"}  # the metrics computed in the pipeline


@dataclass(frozen=True)
class WeekStat:
    week: date
    completed: int
    on_time: int

    @property
    def pct(self) -> float | None:
        return round(100 * self.on_time / self.completed, 1) if self.completed else None


@dataclass
class Stats:
    materials: int
    suppliers: int
    locations: int
    campaigns: int
    batches: int
    lots: int
    lots_by_type: dict[str, int]
    deviations: int
    open_deviations: int
    drug_substance_share: float
    open_rows: int
    released_rows: int
    open_stage_counts: dict[str, int]
    rag_counts: dict[str, int]
    threepl_share: float
    offsite_share: float
    weekly: dict[str, list[WeekStat]] = field(default_factory=dict)


def compute_stats(plan: Plan, profile: SiteProfile) -> Stats:
    lots = plan.lots()
    open_lots = [(b, lot) for b, lot in lots if lot.stage != "released"]
    rag: Counter[str] = Counter()
    for batch, lot in open_lots:
        found = rag_of(profile, batch, lot, plan.need_by.get(batch.matnr), plan.calendar.today)
        if found is not None:
            rag[found] += 1
    sampled = [lot for _, lot in lots if lot.samples]
    weeks = plan.calendar.metric_week_starts
    weekly: dict[str, list[WeekStat]] = {}
    for metric, stage in METRICS.items():
        done: Counter[date] = Counter()
        on_time: Counter[date] = Counter()
        for batch, lot in lots:
            entry, exit_ = stage_dates(batch, lot).get(stage, (None, None))
            if entry is None or exit_ is None:
                continue
            week = plan.calendar.monday(exit_)
            done[week] += 1
            on_time[week] += int((exit_ - entry).days <= sla_for(stage, lot.lot_type, profile))  # type: ignore[arg-type]
        weekly[metric] = [WeekStat(week, done[week], on_time[week]) for week in weeks]
    return Stats(
        materials=len(plan.world.materials),
        suppliers=len(plan.world.suppliers),
        locations=len(plan.world.locations),
        campaigns=len(plan.world.campaigns),
        batches=len(plan.batches),
        lots=len(lots),
        lots_by_type=dict(Counter(lot.lot_type for _, lot in lots)),
        deviations=len(plan.deviations),
        open_deviations=sum(1 for d in plan.deviations if d.closed_on is None),
        drug_substance_share=sum(1 for m in plan.world.materials if m.klass == "drug_substance")
        / len(plan.world.materials),
        open_rows=len(open_lots),
        released_rows=len(lots) - len(open_lots),
        open_stage_counts=dict(Counter(lot.stage for _, lot in open_lots)),
        rag_counts={color: rag[color] for color in ("green", "amber", "red")},
        threepl_share=sum(1 for b in plan.batches if b.received_location_type == "3pl") / len(plan.batches),
        offsite_share=sum(1 for lot in sampled if lot.latest and lot.latest.offsite) / len(sampled),
        weekly=weekly,
    )
