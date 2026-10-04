"""The five story batches (F05-FR-06): fixed set-ups the demo script walks through.

They do not depend on the seed. Every date is an offset from the demo's opening date, so a profile with
another ``demo.start_datetime`` moves them together; for ``site_a`` (opening Monday 2026-10-12) the offsets
give the dates the spec names. Their materials, suppliers, campaigns and need-by dates are reserved here and
the random builders skip them.

| batch | what it shows |
| B1042 | in QC testing, all tests done, LIMS not approved yet (Act 3) |
| B2077 | sampling since 8 Oct, need-by 3 Dec: no compression until the planner pulls it forward (Act 5) |
| B3150 | waiting in QA release with an open major deviation |
| B4410 | re-evaluation lot in sampling; the batch history shows the initial release and 3 re-evals |
| B5003 | LIMS approved 30 hours before opening and no usage decision: an air gap (Act 6) |
"""

from dataclasses import dataclass, field
from datetime import UTC, date, timedelta
from decimal import Decimal

from datagen.model import BatchPlan, DeviationPlan, LotPlan, SamplePlan, TestSpec
from datagen.timeline import Builder

ONSITE_LOCATION = "0100"


@dataclass
class StoryResult:
    batches: list[BatchPlan] = field(default_factory=list)
    need_by: dict[str, tuple[str, date]] = field(default_factory=dict)  # matnr -> (campaign, need-by date)
    deviations: list[DeviationPlan] = field(default_factory=list)


TESTS_B1042 = (
    ("ID", "Identification", "Conforms", "Conforms to reference"),
    ("ASSAY", "Assay", "99.2 %", "98.0-102.0 %"),
    ("WATER", "Water content", "0.31 %", "NMT 0.5 %"),
    ("RS", "Related substances", "0.12 %", "NMT 0.3 %"),
    ("SOLV", "Residual solvents", "Conforms", "Conforms to limits"),
)


def _batch(charg: str, matnr: str, lifnr: str, quantity: int, lots: list[LotPlan]) -> BatchPlan:
    for lot in lots:
        lot.story_id = charg
    return BatchPlan(
        matnr=matnr,
        charg=charg,
        lifnr=lifnr,
        lgort=ONSITE_LOCATION,
        site_lgort=ONSITE_LOCATION,
        received_location_type="onsite",
        quantity=Decimal(quantity),
        lots=lots,
        story_id=charg,
    )


def build_stories(builder: Builder) -> StoryResult:
    cal = builder.calendar
    today = cal.today
    snap = cal.snap_back

    def at(offset: int) -> date:
        return snap(today + timedelta(days=offset))

    def approved_sample(collected: date, approved: date) -> SamplePlan:
        return SamplePlan(collected=collected, started=collected, outcome="approved", closed_on=approved)

    result = StoryResult()

    # B1042: QC testing onsite, all five tests passed, LIMS not approved yet.
    tests = [
        TestSpec(code, name, value, spec, completed_on=at(offset))
        for (code, name, value, spec), offset in zip(TESTS_B1042, (-36, -31, -25, -19, -12), strict=True)
    ]
    lot = LotPlan("", "01", at(-47), "passed", check_done=at(-45), stage="qc_testing")
    lot.samples = [SamplePlan(collected=at(-40), started=at(-40), results=tests)]
    result.batches.append(_batch("B1042", "RM10023", "SUP003", 500, [lot]))
    result.need_by["RM10023"] = ("CMP-ALPHA", today + timedelta(days=9))

    # B2077: onsite delivery in sampling since 8 Oct; system need-by 3 Dec = available time equals the budget.
    lot = LotPlan("", "01", at(-6), "passed", check_done=at(-4), stage="sampling")
    result.batches.append(_batch("B2077", "RM10031", "SUP007", 250, [lot]))
    result.need_by["RM10031"] = ("CMP-BRAVO", today + timedelta(days=52))

    # B3150: approved in LIMS, waiting for the usage decision, with an open major deviation.
    lot = LotPlan("", "01", at(-30), "passed", check_done=at(-28), stage="qa_release")
    lot.samples = [approved_sample(at(-23), at(-6))]
    result.batches.append(_batch("B3150", "RM10045", "SUP011", 1000, [lot]))
    result.need_by["RM10045"] = ("CMP-CEDAR", today + timedelta(days=2))
    result.deviations.append(
        DeviationPlan(
            title="Impurity result out of trend",
            description="Impurity result out of trend. Recorded at site; impact is being assessed.",
            severity="major",
            opened_on=at(-4),
            closed_on=None,
            root_cause_category="Not yet determined",
            owner="QA",
            links=[("RM10045", "B3150")],
            story_id="B3150",
        )
    )

    # B4410: the open re-evaluation lot started on the Thursday before opening; the earlier ones 8, 16 and
    # 24 weeks before it. All earlier lots are released.
    current_start = at(-4)
    lots: list[LotPlan] = []
    first = snap(current_start - timedelta(days=168 + 90))
    parent = LotPlan("", "01", first, "passed", check_done=snap(first + timedelta(days=6)), stage="released")
    parent.samples = [approved_sample(snap(first + timedelta(days=13)), snap(first + timedelta(days=50)))]
    parent.ud_code, parent.ud_date = "A", snap(first + timedelta(days=57))
    lots.append(parent)
    for weeks in (24, 16, 8):
        start = current_start - timedelta(days=7 * weeks)
        collected = snap(start + timedelta(days=4))
        approved = snap(collected + timedelta(days=24))
        earlier = LotPlan("", "09", start, "none", stage="released")
        earlier.samples = [approved_sample(collected, approved)]
        earlier.ud_code, earlier.ud_date = "A", snap(approved + timedelta(days=3))
        lots.append(earlier)
    lots.append(LotPlan("", "09", current_start, "none", stage="sampling"))
    result.batches.append(_batch("B4410", "RM10052", "SUP021", 100, lots))
    result.need_by["RM10052"] = ("CMP-DELTA", today + timedelta(days=40))

    # B5003: LIMS approved 30 hours before the opening instant and no usage decision: an air gap.
    approved_at = builder.profile.demo.start_datetime.astimezone(UTC) - timedelta(hours=30)
    lot = LotPlan("", "01", at(-55), "passed", check_done=at(-53), stage="qa_release")
    sample = approved_sample(at(-48), approved_at.astimezone(builder.profile.site.tz).date())
    sample.approved_at = approved_at
    lot.samples = [sample]
    result.batches.append(_batch("B5003", "RM10067", "SUP030", 750, [lot]))
    result.need_by["RM10067"] = ("CMP-ALPHA", today + timedelta(days=10))
    return result
