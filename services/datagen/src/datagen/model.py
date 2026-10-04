"""The plan: a complete, in-memory description of the site history, before anything touches a database.

Planning is pure (seeded, no I/O). ``datagen.events`` turns a plan into dated event-function calls and
``datagen.executor`` replays them. Keeping the plan separate makes the distribution, quirk and story checks
fast, deterministic unit tests.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal

from datagen.world import World

ACCEPT_CODES = ("A", "A4")
REJECT_CODE = "R"


@dataclass(frozen=True)
class Calendar:
    """Business dates around the demo's opening instant (a Monday morning in site_a)."""

    today: date  # the demo's opening date, site-local
    weeks: int  # length of the simulated history
    metric_weeks: int

    @staticmethod
    def snap_back(day: date) -> date:
        """The weekday on or before ``day``."""
        while day.weekday() >= 5:
            day -= timedelta(days=1)
        return day

    @staticmethod
    def monday(day: date) -> date:
        return day - timedelta(days=day.weekday())

    @property
    def last_day(self) -> date:
        """The last business day before opening: no event is dated later (except explicit story times)."""
        return self.snap_back(self.today - timedelta(days=1))

    @property
    def this_week(self) -> date:
        return self.monday(self.today)

    @property
    def history_weeks(self) -> list[date]:
        """Mondays of the complete weeks of the history, oldest first."""
        return [self.this_week - timedelta(days=7 * n) for n in range(self.weeks, 0, -1)]

    @property
    def metric_week_starts(self) -> list[date]:
        """Mondays of the weeks the pipeline publishes for M3, M6 and M7 (last complete weeks)."""
        return self.history_weeks[-self.metric_weeks :]


@dataclass
class TestSpec:
    """One seeded test result (story batches only)."""

    __test__ = False  # not a pytest class
    code: str
    name: str
    value: str
    spec: str
    status: str = "pass"


@dataclass
class SamplePlan:
    collected: date
    offsite: bool = False
    lab: str | None = None
    shipped: date | None = None
    started: date | None = None  # testing started (sample in progress)
    outcome: str = "open"  # open | approved | rejected
    closed_on: date | None = None  # approval or rejection date
    approved_at: datetime | None = None  # explicit approval instant (story B5003); default: closed_on
    results: list[TestSpec] = field(default_factory=list)


@dataclass
class LotPlan:
    ref: str  # "<matnr>|<charg>|01" or "...|09-<n>": stable until the DB numbers it
    lot_type: str  # 01 initial, 09 re-evaluation
    start: date  # goods receipt date (01) or lot start (09)
    check: str  # open | passed | failed | none
    check_done: date | None = None
    transfer: date | None = None  # 311 from the 3PL to site
    samples: list[SamplePlan] = field(default_factory=list)  # oldest first; the last is the latest
    ud_code: str | None = None
    ud_date: date | None = None
    reversed_same_day: bool = False  # goods receipt cancelled the day it was posted
    stage: str = ""  # the intended stage at demo start
    story_id: str | None = None
    tags: list[str] = field(default_factory=list)  # quirk labels, for the report

    @property
    def latest(self) -> SamplePlan | None:
        return self.samples[-1] if self.samples else None


@dataclass
class BatchPlan:
    matnr: str
    charg: str
    lifnr: str
    lgort: str  # receiving storage location
    site_lgort: str  # onsite location the stock ends up in (the 3PL transfer target, or lgort itself)
    received_location_type: str  # onsite | 3pl
    quantity: Decimal
    lots: list[LotPlan] = field(default_factory=list)
    holds: list[tuple[date, bool]] = field(default_factory=list)  # (day, hold on/off)
    blocks: list[tuple[date, bool]] = field(default_factory=list)  # (day, block/unblock)
    story_id: str | None = None

    @property
    def first_day(self) -> date:
        return self.lots[0].start


@dataclass
class DemandPlan:
    matnr: str
    campaign: str
    requirement_date: date
    quantity: Decimal
    created_on: date
    closed_on: date | None = None  # set when the line was closed again


@dataclass
class DeviationPlan:
    title: str
    description: str
    severity: str
    opened_on: date
    closed_on: date | None
    root_cause_category: str
    owner: str
    links: list[tuple[str, str]]  # (material, batch)
    story_id: str | None = None


@dataclass
class Plan:
    seed: int
    calendar: Calendar
    world: World
    batches: list[BatchPlan] = field(default_factory=list)
    demands: list[DemandPlan] = field(default_factory=list)
    deviations: list[DeviationPlan] = field(default_factory=list)
    need_by: dict[str, date | None] = field(
        default_factory=dict
    )  # per material: the system need-by at opening

    def lots(self) -> list[tuple[BatchPlan, LotPlan]]:
        return [(batch, lot) for batch in self.batches for lot in batch.lots]


def derive_stage(batch: BatchPlan, lot: LotPlan) -> str:
    """The stage engine rules of 03-domain-model section 4, applied to the plan's facts (first match wins).

    This is the generator's own check that its intended stage labels are what the rules will give. It reads
    the planned facts, never the databases, and it is not the pipeline's stage engine (that is F06).
    """
    started = lot.start if not lot.reversed_same_day else None  # a netted receipt has no cycle start
    latest = lot.latest
    lims = "none" if latest is None else {"open": "in_progress"}.get(latest.outcome, latest.outcome)
    offsite = latest.offsite if latest is not None else False
    collected = latest.collected if latest is not None else None
    shipped = latest.shipped if latest is not None else None
    ud_effective = lot.ud_code in ACCEPT_CODES
    if ud_effective:
        return "released"
    if lims == "approved":
        return "qa_release"
    if lims != "approved" and ((not offsite and collected is not None) or (offsite and shipped is not None)):
        return "qc_testing"
    if offsite and collected is not None and shipped is None:
        return "qc_ship"
    if started is not None and lot.check in ("open", "failed"):
        return "receipt"
    if started is not None and batch.received_location_type == "3pl" and lot.transfer is None:
        return "call_off"
    if started is not None:
        return "sampling"
    return "pending"


def current_stage_entry(batch: BatchPlan, lot: LotPlan) -> date | None:
    """Entry date of the lot's current stage (03 section 4, stage entry table). None for pending/released."""
    latest = lot.latest
    match lot.stage:
        case "receipt":
            return lot.start
        case "call_off":
            return lot.check_done or lot.start
        case "sampling":
            if batch.received_location_type == "3pl" and lot.lot_type == "01":
                return lot.transfer
            return lot.check_done or lot.start  # a 09 lot has no check: the receipt exits on its start
        case "qc_ship":
            return latest.collected if latest else None
        case "qc_testing":
            if latest is None:
                return None
            return latest.shipped if latest.offsite else latest.collected
        case "qa_release":
            return latest.closed_on if latest else None
        case _:
            return None


def sampling_entry(batch: BatchPlan, lot: LotPlan) -> date | None:
    """Entry date of the sampling stage (03 section 4, stage entry table)."""
    if lot.lot_type == "01" and batch.received_location_type == "3pl":
        return lot.transfer
    return lot.check_done or lot.start


def weekdays_between(first: date, last: date) -> list[date]:
    """Business days from ``first`` to ``last``, both included."""
    days = (first + timedelta(days=n) for n in range((last - first).days + 1))
    return [day for day in days if day.weekday() < 5]
