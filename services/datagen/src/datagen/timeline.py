"""The timeline planner: builds the whole site history as a ``Plan`` (F05-FR-03, FR-04).

The generator is target-driven. Instead of simulating arrivals and hoping the stage mix comes out right, it
decides each lot's *current* state first (which stage an open lot is in and for how long, or when a released
lot got its usage decision) and then builds the earlier stages backward in time from that anchor. Stage
durations are lognormal around the SLA; whether a stage is on time follows a per-week target so that the
weekly M3 / M6 / M7 percentages land in the intended band.

Planning is pure: seeded streams, no database, no clock.
"""

import math
import random
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from r2r_core.profile import SiteProfile
from r2r_core.sla import sla_for

from datagen.model import (
    ACCEPT_CODES,
    BatchPlan,
    Calendar,
    LotPlan,
    SamplePlan,
    derive_stage,
)
from datagen.params import Durations, Params
from datagen.rng import stream
from datagen.world import World

METRIC_STAGES = ("sampling", "qc_testing", "qa_release")  # M3, M6, M7
OPEN_SAMPLED_STAGES = ("sampling", "qc_ship", "qc_testing", "qa_release")  # where a 09 lot can be open


def allocate(total: int, shares: dict[str, float]) -> dict[str, int]:
    """Split ``total`` over ``shares`` in proportion, by largest remainder (so the parts add up exactly)."""
    raw = {key: total * share for key, share in shares.items()}
    counts = {key: int(value) for key, value in raw.items()}
    leftover = total - sum(counts.values())
    for key in sorted(raw, key=lambda k: (raw[k] - counts[k], k), reverse=True)[:leftover]:
        counts[key] += 1
    return counts


def stage_sequence(lot_type: str, threepl: bool, offsite: bool) -> list[str]:
    """The stages a lot passes through, in order (03 section 4, "Applicable stages")."""
    stages = [] if lot_type == "09" else ["receipt"]
    if lot_type == "01" and threepl:
        stages.append("call_off")
    stages.append("sampling")
    if offsite:
        stages.append("qc_ship")
    stages.extend(["qc_testing", "qa_release"])
    return stages


def draw_days(rng: random.Random, cfg: Durations, sla: int, on_time: bool) -> int:
    """A stage duration in days: lognormal around the SLA, from the on-time or the late side of it."""
    if on_time:
        for _ in range(60):
            days = round(rng.lognormvariate(math.log(max(1.0, sla * cfg.on_time_centre)), cfg.sigma))
            if 1 <= days <= sla:
                return days
        return max(1, sla)
    extra = round(rng.lognormvariate(math.log(max(1.0, sla * cfg.late_centre)), cfg.late_sigma))
    return min(sla + max(1, extra), int(sla * 3.5) + 2)


class OnTimeBook:
    """Keeps each metric week's on-time share on its target, completion by completion.

    The decision rule is error diffusion: a completion is on time while the running on-time count is below
    the target share of the completions so far plus this one (minus half). The final count of every week is
    then within one half of ``target x completions``, however the completions arrive.
    """

    def __init__(self, calendar: Calendar, params: Params, rng: random.Random) -> None:
        self.calendar = calendar
        self.default = params.on_time.default
        self.targets = {
            (stage, week): rng.uniform(params.on_time.weekly_min, params.on_time.weekly_max)
            for stage in METRIC_STAGES
            for week in calendar.metric_week_starts
        }
        self.counts: dict[tuple[str, date], list[int]] = {}

    def wants_on_time(self, stage: str, exit_date: date, rng: random.Random) -> bool:
        key = (stage, self.calendar.monday(exit_date))
        if key not in self.targets:
            return rng.random() < self.default
        done, on_time = self.counts.get(key, [0, 0])
        return on_time + 0.5 <= self.targets[key] * (done + 1)

    def record(self, stage: str, exit_date: date, on_time: bool) -> None:
        key = (stage, self.calendar.monday(exit_date))
        if key in self.targets:
            tally = self.counts.setdefault(key, [0, 0])
            tally[0] += 1
            tally[1] += int(on_time)


@dataclass(frozen=True)
class LotSpec:
    """What to build: a lot of ``lot_type`` that is open in ``stage`` since ``anchor``, or released on it."""

    lot_type: str
    threepl: bool
    offsite: bool
    stage: str | None  # None: released
    anchor: date  # entry date of ``stage`` (open) or the usage decision date (released)


class Builder:
    def __init__(self, profile: SiteProfile, params: Params, seed: int, world: World) -> None:
        self.profile, self.params, self.seed, self.world = profile, params, seed, world
        today = profile.demo.start_datetime.astimezone(profile.site.tz).date()
        self.calendar = Calendar(today, params.history.weeks, params.history.metric_weeks)
        self.rng = stream(seed, "timeline")
        self.book = OnTimeBook(self.calendar, params, stream(seed, "ontime"))
        self.released_in_week: Counter[date] = Counter()
        self.weekly_target: dict[date, int] = {}
        for week in self.calendar.history_weeks:
            low, high = (
                params.completions.recent_release_per_week
                if week in self.calendar.metric_week_starts
                else params.completions.early_release_per_week
            )
            self.weekly_target[week] = self.rng.randint(low, high)
        self.provisional_threepl = 0.22
        self.provisional_offsite = 0.10

    # --- durations and anchors ------------------------------------------------------------------

    def _step_back(self, stage: str, lot_type: str, exit_date: date) -> date:
        """Entry date of ``stage`` given its exit date, drawing the duration and booking the outcome."""
        sla = sla_for(stage, lot_type, self.profile)  # type: ignore[arg-type]
        wanted = (
            self.book.wants_on_time(stage, exit_date, self.rng)
            if stage in METRIC_STAGES
            else self.rng.random() < self.params.on_time.default
        )
        entry, actual = exit_date, 0
        for _ in range(12):
            days = draw_days(self.rng, self.params.durations, sla, wanted)
            entry = self.calendar.snap_back(exit_date - timedelta(days=days))
            actual = (exit_date - entry).days
            if (actual <= sla) == wanted:
                break
        if stage in METRIC_STAGES:
            self.book.record(stage, exit_date, actual <= sla)
        return entry

    def open_anchor(self, stage: str, lot_type: str) -> date:
        """Entry date of an open lot's current stage: inside the SLA, or backlog beyond it."""
        cfg = self.params.stage_age[stage]
        sla = sla_for(stage, lot_type, self.profile)  # type: ignore[arg-type]
        if self.rng.random() < cfg.within_sla:
            age = self.rng.randint(3, max(3, sla))
        else:
            backlog = max(
                1, int(self.rng.triangular(1, max(2, cfg.backlog_max_days), cfg.backlog_max_days / 3))
            )
            age = sla + backlog
        return self.calendar.snap_back(self.calendar.today - timedelta(days=age))

    def release_day(self, week: date) -> date:
        return week + timedelta(days=self.rng.randint(0, 4))

    # --- lot construction -----------------------------------------------------------------------

    def build_lot(self, spec: LotSpec, ref: str) -> LotPlan:
        """Build one lot backward from its anchor, then label it with the stage the rules give."""
        sequence = stage_sequence(spec.lot_type, spec.threepl, spec.offsite)
        reached = len(sequence) if spec.stage is None else sequence.index(spec.stage)
        bounds: list[date] = [spec.anchor] * (reached + 1)
        for index in range(reached - 1, -1, -1):
            bounds[index] = self._step_back(sequence[index], spec.lot_type, bounds[index + 1])
        lot = LotPlan(
            ref=ref,
            lot_type=spec.lot_type,
            start=bounds[0],
            check="none" if spec.lot_type == "09" else "open",
        )
        sample: SamplePlan | None = None
        for index in range(1, reached + 1):
            done, day = sequence[index - 1], bounds[index]
            if done == "receipt":
                lot.check, lot.check_done = "passed", day
            elif done == "call_off":
                lot.transfer = day
            elif done == "sampling":
                sample = SamplePlan(
                    collected=day, offsite=spec.offsite, lab=self._lab() if spec.offsite else None
                )
                if not spec.offsite:
                    sample.started = day
                lot.samples.append(sample)
            elif done == "qc_ship":
                assert sample is not None
                sample.shipped = sample.started = day
            elif done == "qc_testing":
                assert sample is not None
                sample.outcome, sample.closed_on = "approved", day
            elif done == "qa_release":
                lot.ud_code = self.rng.choices(ACCEPT_CODES, weights=[85, 15])[0]
                lot.ud_date = day
        lot.stage = "released" if spec.stage is None else spec.stage
        return lot

    def _lab(self) -> str:
        return self.rng.choice(self.world.labs)

    def build_pending(self, ref: str) -> LotPlan:
        """A goods receipt reversed the day it was posted and not received again (F05-FR-03, OQ-035)."""
        age = self.rng.randint(3, 60)
        day = self.calendar.snap_back(self.calendar.today - timedelta(days=age))
        return LotPlan(
            ref=ref, lot_type="01", start=day, check="open", reversed_same_day=True, stage="pending"
        )

    def note_release(self, lot: LotPlan) -> None:
        if lot.ud_date is not None:
            self.released_in_week[self.calendar.monday(lot.ud_date)] += 1

    def new_batch(self, threepl: bool, onsite_only: bool = False) -> BatchPlan:
        """A batch with no material yet (assigned later, once all batches exist) and no lots."""
        onsite = self.rng.choice(self.world.onsite).lgort
        lgort = self.rng.choice(self.world.threepl).lgort if threepl and not onsite_only else onsite
        quantity = Decimal(self.rng.choice(self.params.quirks.quantities)) * self.rng.choice([1, 1, 1, 2])
        return BatchPlan(
            matnr="",
            charg="",
            lifnr="",
            lgort=lgort,
            site_lgort=onsite,
            received_location_type="3pl" if lgort != onsite else "onsite",
            quantity=quantity,
        )

    def verify(self, batch: BatchPlan, lot: LotPlan) -> None:
        derived = derive_stage(batch, lot)
        if derived != lot.stage:
            raise AssertionError(f"{lot.ref}: intended {lot.stage} but the rules give {derived}")


def weighted_choice(rng: random.Random, weights: dict[str, float]) -> str:
    return rng.choices(list(weights), weights=list(weights.values()))[0]


def pick_weeks(rng: random.Random, weeks: Sequence[date], target: dict[date, int]) -> date:
    return rng.choices(list(weeks), weights=[target[w] for w in weeks])[0]
