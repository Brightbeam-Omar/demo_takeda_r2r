"""T8: a full run on the seeded dataset (F07-AC-01, F07-AC-02, F07-AC-05, F07-FR-08). Needs Postgres.

Generates the F05 dataset into throwaway databases, runs all six steps in-process (no Dagster, no webhook) and
checks the published objects and the run time of the steps.
"""

import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, date, timedelta
from pathlib import Path

import pytest
from datagen.executor import Databases
from datagen.generate import generate
from datagen.params import load_params
from erp_sim.db import migrate as migrate_erp
from lims_sim.db import migrate as migrate_lims
from qms_sim.db import migrate as migrate_qms
from r2r_core import clock
from r2r_core.clock import FixedClock
from r2r_core.profile import SiteProfile, load_profile
from r2r_core.reports import ReleasedLot, expedite_on_time, needs_by_adherence
from r2r_pipeline.context import SourceDsns
from r2r_pipeline.lake import read_delta
from r2r_pipeline.pipeline import run_pipeline
from r2r_pipeline.publish import PUBLISH_ORDER

pytestmark = pytest.mark.integration


@dataclass
class Run:
    lake: Path
    profile: SiteProfile
    seconds: float
    first_snapshot_rows: int


@pytest.fixture(scope="module")
def run(
    make_test_database: Callable[[str], str],
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch_module: pytest.MonkeyPatch,
) -> Iterator[Run]:
    monkeypatch_module.delenv("WEBHOOK_URL", raising=False)
    profile = load_profile("site_a")
    erp, lims, qms = (make_test_database(f"pipeline_pub_{name}") for name in ("erp", "lims", "qms"))
    migrate_erp(erp)
    migrate_lims(lims)
    migrate_qms(qms)
    lake = tmp_path_factory.mktemp("lake")
    dsns = SourceDsns(erp, lims, qms)
    generate(
        profile, load_params(), profile.demo.seed, Databases(erp, lims, qms), tmp_path_factory.mktemp("a")
    )
    clock.set_clock_source(FixedClock(profile.demo.start_datetime.astimezone(UTC)))
    try:
        began = time.perf_counter()
        run_pipeline(profile, lake, run_id="run-1", dsns=dsns)
        seconds = time.perf_counter() - began
        first = read_delta(lake, "intelligence.batch_snapshot").num_rows
        run_pipeline(profile, lake, run_id="run-2", dsns=dsns)  # a second run on the same demo day
        yield Run(lake, profile, seconds, first)
    finally:
        clock.set_clock_source(None)


@pytest.fixture(scope="module")
def monkeypatch_module() -> Iterator[pytest.MonkeyPatch]:
    patch = pytest.MonkeyPatch()
    yield patch
    patch.undo()


def test_f07_fr08_the_six_steps_take_far_less_than_sixty_seconds_in_process(run: Run) -> None:
    assert run.seconds < 60, f"{run.seconds:.1f} s"


def test_f07_ac01_all_published_objects_exist_with_the_second_run_id(run: Run) -> None:
    for name in PUBLISH_ORDER:
        assert read_delta(run.lake, f"published.{name}").num_rows > 0, name
    [status] = read_delta(run.lake, "published.pipeline_status_v").to_pylist()
    assert status["last_run_id"] == "run-2"
    assert status["row_count"] == read_delta(run.lake, "published.batch_pipeline_v").num_rows > 600


def test_f07_ac02_two_runs_on_the_same_day_give_the_same_snapshot_rows(run: Run) -> None:
    snapshot = read_delta(run.lake, "intelligence.batch_snapshot")
    assert snapshot.num_rows == run.first_snapshot_rows
    assert set(snapshot["run_id"].to_pylist()) == {"run-2"}


def test_f07_fr01_the_locked_need_by_is_set_for_rows_with_demand(run: Run) -> None:
    rows = read_delta(run.lake, "published.batch_pipeline_v").to_pylist()
    with_demand = [r for r in rows if r["system_need_by_date"] is not None]
    assert with_demand
    assert all(
        r["system_need_by_locked"] == r["system_need_by_date"] for r in with_demand
    )  # first run of the day
    assert read_delta(run.lake, "intelligence.need_by_history").num_rows == len(
        {r["row_key"] for r in rows if r["system_need_by_locked"] is not None}
    )


def test_f07_ac05_app_side_metrics_are_awaiting_signal(run: Run) -> None:
    reference = {r["metric_id"]: r for r in read_delta(run.lake, "published.metric_reference_v").to_pylist()}
    assert {m for m, r in reference.items() if r["status"] == "awaiting_signal"} == {"M1", "M2", "M4", "M5"}
    assert all(reference[m]["null_reason"] for m in ("M1", "M2", "M4", "M5"))


def test_f07_fr02_the_seeded_history_has_enough_completions_for_every_pipeline_metric(run: Run) -> None:
    """F05 promises at least 10 completions per week for M3, M6 and M7 across the last 12 complete metric weeks (F20 keeps 52)."""
    start = run.profile.demo.start_datetime.date()
    last_complete = start - timedelta(days=start.weekday() + 7)
    weekly = read_delta(run.lake, "published.weekly_metrics_v").to_pylist()
    for metric in ("M3", "M6", "M7"):
        rows = {r["week_start"]: r for r in weekly if r["metric_id"] == metric}
        assert len(rows) == 53
        recent = last_complete - timedelta(weeks=11)
        complete = [r for week, r in rows.items() if recent <= week <= last_complete]
        assert all(r["completed"] >= 10 for r in complete), (metric, [r["completed"] for r in complete])
        assert rows[last_complete]["pct"] is not None
    assert date(2026, 10, 5) == last_complete


def test_f20_ac04_the_latest_day_of_pipeline_daily_equals_the_open_non_pending_rows(run: Run) -> None:
    """F20-AC-04: the stacked total of the snapshot day is every open lot that has a stage (468 at demo start)."""
    day = run.profile.demo.start_datetime.date()
    batch = read_delta(run.lake, "published.batch_pipeline_v").to_pylist()
    current = {}
    for row in batch:
        if row["stage_key"] not in ("pending", "released"):
            current[row["stage_key"]] = current.get(row["stage_key"], 0) + 1
    last = {
        r["stage_key"]: r["open_count"]
        for r in read_delta(run.lake, "published.pipeline_daily_v").to_pylist()
        if r["day"] == day
    }
    assert {k: v for k, v in last.items() if v} == current
    assert sum(last.values()) == sum(current.values()) == 468


def _released_lots(run: Run) -> list[ReleasedLot]:
    return [
        ReleasedLot(r["row_key"], r["ud_date"], True, r["need_by_at_release"], r["expedite_due_date"])
        for r in read_delta(run.lake, "published.batch_pipeline_v").to_pylist()
        if r["ud_effective"]
    ]


def test_f20_oq122_the_seeded_adherence_is_amber_and_every_released_lot_has_a_need_by(run: Run) -> None:
    result = needs_by_adherence(_released_lots(run), [], 2026)
    assert result.excluded == 0
    assert result.pct is not None and 85 <= result.pct < 90, result
    lots = _released_lots(run)
    assert len(lots) == 321  # the F05 released rows; the older ones fall in earlier years
    assert (result.on_time + result.late) == result.total == sum(1 for r in lots if r.ud_date.year == 2026)


def test_f20_oq122_the_seeded_expedites_are_four_with_three_on_time(run: Run) -> None:
    result = expedite_on_time(_released_lots(run), set(), 2026)
    assert (result.on_time, result.late, result.expedited) == (3, 1, 4)


def test_f20_oq122_the_f05_counts_and_week_41_are_unchanged(run: Run) -> None:
    """803 lots, 650 batches, 482 open and 321 released; week 41 is M3 94, M6 84 and M7 69 (F20-FR-07)."""
    rows = read_delta(run.lake, "published.batch_pipeline_v").to_pylist()
    assert len(rows) == 803
    assert len({(r["material_no"], r["batch_no"]) for r in rows}) == 650
    assert sum(1 for r in rows if r["stage_key"] != "released") == 482
    assert sum(1 for r in rows if r["stage_key"] == "released") == 321
    week = {
        r["metric_id"]: r
        for r in read_delta(run.lake, "published.weekly_metrics_v").to_pylist()
        if str(r["week_start"]) == "2026-10-05"
    }
    assert {m: round(week[m]["pct"]) for m in ("M3", "M6", "M7")} == {"M3": 94, "M6": 84, "M7": 69}
