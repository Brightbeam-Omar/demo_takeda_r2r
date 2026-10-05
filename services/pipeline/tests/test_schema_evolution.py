"""F07 deviation: a column added to a contract is picked up by the next run, with no lakehouse reset."""

from datetime import UTC, date, datetime
from pathlib import Path

import pyarrow as pa
import pytest
from fixture_world import World
from r2r_core import clock
from r2r_core.clock import FixedClock
from r2r_core.profile import SiteProfile
from r2r_pipeline import publish, snapshot
from r2r_pipeline.lake import read_delta
from test_publish import run_all, table

pytestmark = pytest.mark.integration


def test_f07_a_new_published_column_needs_no_reset(
    tmp_path: Path, profile: SiteProfile, monkeypatch: pytest.MonkeyPatch
) -> None:
    world = World()
    world.receive("B1", "10000001", date(2026, 10, 1))
    world.demand(1, date(2026, 11, 20))
    clock.set_clock_source(FixedClock(datetime(2026, 10, 12, 7, 0, tzinfo=UTC)))
    try:
        run_all(world, tmp_path, profile, "run-1")
        assert "extra_flag" not in table(tmp_path, "batch_pipeline_v")[0]

        original = snapshot.build_snapshot

        def with_extra(*args: object, **kwargs: object) -> pa.Table:
            built: pa.Table = original(*args, **kwargs)  # type: ignore[arg-type]
            return built.append_column("extra_flag", pa.array([True] * built.num_rows))

        monkeypatch.setattr(snapshot, "build_snapshot", with_extra)
        monkeypatch.setattr(publish, "STAGE_COLUMNS", (*publish.STAGE_COLUMNS, "extra_flag"))
        clock.set_clock_source(FixedClock(datetime(2026, 10, 13, 7, 0, tzinfo=UTC)))
        run_all(world, tmp_path, profile, "run-2")  # no reset in between
    finally:
        clock.set_clock_source(None)

    assert table(tmp_path, "batch_pipeline_v")[0]["extra_flag"] is True
    history = {
        r["snapshot_date"]: r["extra_flag"]
        for r in read_delta(tmp_path, "intelligence.batch_snapshot").to_pylist()
    }
    assert history == {date(2026, 10, 12): None, date(2026, 10, 13): True}  # older dates are NULL
    assert [r["last_run_id"] for r in table(tmp_path, "pipeline_status_v")] == ["run-2"]
