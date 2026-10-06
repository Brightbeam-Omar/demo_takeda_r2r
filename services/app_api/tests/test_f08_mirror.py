"""F08-FR-05, FR-05b, FR-10: mirror replace, watermark, no-op, mixed-state check and rollback.

Covers F08-AC-04 (completed after a stale reclaim), AC-05, AC-06 and AC-08.
"""

from decimal import Decimal
from typing import Any

import pytest
from app_api.models import MIRRORS, SyncEvent
from app_api.sync import mirror
from app_api.sync.drain import drain_once
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker
from support import STAMP, FakeReader, published, queue

pytestmark = pytest.mark.integration


def event(factory: sessionmaker[Session], event_id: int) -> SyncEvent:
    with factory() as session:
        row = session.get(SyncEvent, event_id)
        assert row is not None
        return row


def count(factory: sessionmaker[Session], table: str) -> int:
    with factory() as session:
        return int(session.execute(text(f"SELECT count(*) FROM {table}")).scalar_one())


def watermarks(factory: sessionmaker[Session]) -> dict[str, str]:
    with factory() as session:
        return dict(session.execute(text("SELECT object_name, run_id FROM watermark")).tuples().all())


def mirror_runs(factory: sessionmaker[Session]) -> set[str]:
    with factory() as session:
        return {
            row[0]
            for table, *_ in MIRRORS.values()
            for row in session.execute(text(f"SELECT DISTINCT contract_run_id FROM {table}"))
        }


def sync(factory: sessionmaker[Session], reader: FakeReader, run_id: str = "x") -> SyncEvent:
    event_id = queue(factory, run_id)
    drain_once(factory, reader)
    return event(factory, event_id)


def test_f08_fr05_first_sync_replaces_every_mirror_and_sets_the_watermark(
    app_factory: sessionmaker[Session],
) -> None:
    done = sync(app_factory, FakeReader(published("run-A")))
    assert (done.status, done.error) == ("done", None)
    expected = {"batch_pipeline_v": 3, "weekly_metrics_v": 3, "weekly_metric_rows_v": 3, "pipeline_status_v": 1,
                "stage_reference_v": 3, "metric_reference_v": 3, "reason_codes_v": 3, "deviations_v": 0, "expected_deliveries_v": 3}  # fmt: skip
    for name, (table, *_) in MIRRORS.items():
        assert count(app_factory, table) == expected[name], table
    assert done.rows_upserted == sum(expected.values())
    assert done.finished_at is not None
    assert watermarks(app_factory) == dict.fromkeys(MIRRORS, "run-A")
    assert mirror_runs(app_factory) == {"run-A"}


def test_f08_fr05_values_are_copied_and_json_columns_become_jsonb(app_factory: sessionmaker[Session]) -> None:
    sync(app_factory, FakeReader(published("run-A")))
    with app_factory() as session:
        row = session.execute(
            text("SELECT applicable_sla_json->>'n', open_deviation_count, lims_approved_at, offsite_test, "
                 "mirrored_at IS NOT NULL FROM mirror_batch_pipeline WHERE row_key = 'row_key-1'")
        ).one()  # fmt: skip
        status = session.execute(
            text("SELECT source_freshness_json->>'n' FROM mirror_pipeline_status")
        ).scalar_one()
        pct = session.execute(text("SELECT pct FROM mirror_weekly_metrics LIMIT 1")).scalar_one()
    assert tuple(row) == ("1", 1, STAMP, False, True)
    assert status == "0"
    assert pct == Decimal("90.5")


def test_f08_fr05_a_new_run_replaces_the_old_rows_completely(app_factory: sessionmaker[Session]) -> None:
    sync(app_factory, FakeReader(published("run-A", size=3)))
    done = sync(app_factory, FakeReader(published("run-B", size=2)), run_id="run-B")
    assert done.status == "done"
    assert count(app_factory, "mirror_batch_pipeline") == 2
    assert mirror_runs(app_factory) == {"run-B"}
    assert set(watermarks(app_factory).values()) == {"run-B"}


def test_f08_ac05_a_duplicate_webhook_completes_as_a_no_op(app_factory: sessionmaker[Session]) -> None:
    reader = FakeReader(published("run-A"))
    sync(app_factory, reader)
    with app_factory() as session:
        before = session.execute(text("SELECT min(mirrored_at) FROM mirror_batch_pipeline")).scalar_one()
    second = sync(app_factory, reader)
    assert (second.status, second.rows_upserted) == ("done", 0)
    with app_factory() as session:
        after = session.execute(text("SELECT min(mirrored_at) FROM mirror_batch_pipeline")).scalar_one()
    assert before == after  # nothing was rewritten


def test_f08_ac06_a_failure_mid_upsert_keeps_the_previous_mirror_and_fails_the_event(
    app_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    sync(app_factory, FakeReader(published("run-A", size=3)))
    real = mirror._insert_rows
    calls: list[str] = []

    def flaky(session: Session, table: Any, records: list[dict[str, Any]]) -> None:
        calls.append(table.name)
        if len(calls) == 4:
            raise RuntimeError("injected failure")
        real(session, table, records)

    monkeypatch.setattr(mirror, "_insert_rows", flaky)
    failed = sync(app_factory, FakeReader(published("run-B", size=2)), run_id="run-B")
    assert failed.status == "failed"
    assert failed.error is not None
    assert "injected failure" in failed.error
    assert failed.finished_at is not None
    assert count(app_factory, "mirror_batch_pipeline") == 3
    assert mirror_runs(app_factory) == {"run-A"}
    assert set(watermarks(app_factory).values()) == {"run-A"}


def test_f08_fr05_readers_see_the_old_mirror_until_commit(
    app_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    sync(app_factory, FakeReader(published("run-A", size=3)))
    real = mirror._insert_rows
    seen: list[int] = []

    def peeking(session: Session, table: Any, records: list[dict[str, Any]]) -> None:
        real(session, table, records)
        with app_factory() as other:  # a second connection must not block on the replace (no TRUNCATE lock)
            other.execute(text("SET LOCAL lock_timeout = '1s'"))
            seen.append(int(other.execute(text("SELECT count(*) FROM mirror_batch_pipeline")).scalar_one()))

    monkeypatch.setattr(mirror, "_insert_rows", peeking)
    sync(app_factory, FakeReader(published("run-B", size=2)), run_id="run-B")
    assert seen and set(seen) == {3}
    assert count(app_factory, "mirror_batch_pipeline") == 2


@pytest.mark.parametrize(
    "stale_object", ["batch_pipeline_v", "weekly_metrics_v", "weekly_metric_rows_v", "expected_deliveries_v"]
)
def test_f08_ac08_a_mixed_publish_fails_the_event_and_leaves_the_mirror_alone(
    app_factory: sessionmaker[Session], stale_object: str
) -> None:
    sync(app_factory, FakeReader(published("run-A")))
    mixed = published("run-B")
    mixed[stale_object] = published("run-A")[stale_object]  # that object still holds the previous run
    failed = sync(app_factory, FakeReader(mixed), run_id="run-B")
    assert failed.status == "failed"
    assert failed.error is not None
    assert stale_object in failed.error
    assert "run-A" in failed.error
    assert mirror_runs(app_factory) == {"run-A"}
    assert set(watermarks(app_factory).values()) == {"run-A"}


def test_f08_ac08_one_stale_row_among_current_rows_is_a_mixed_state(
    app_factory: sessionmaker[Session],
) -> None:
    data = published("run-B")
    data["batch_pipeline_v"][1]["run_id"] = "run-A"
    failed = sync(app_factory, FakeReader(data), run_id="run-B")
    assert failed.status == "failed"
    assert count(app_factory, "mirror_batch_pipeline") == 0


def test_f08_fr10_the_mixed_state_check_runs_before_the_no_op_check(
    app_factory: sessionmaker[Session],
) -> None:
    sync(app_factory, FakeReader(published("run-A")))
    crashed_publish = published("run-A")
    crashed_publish["batch_pipeline_v"] = published("run-B")["batch_pipeline_v"]  # status still says run-A
    failed = sync(app_factory, FakeReader(crashed_publish))
    assert failed.status == "failed"


def test_f08_fr10_empty_and_reference_objects_count_as_consistent(app_factory: sessionmaker[Session]) -> None:
    data = published("run-A", weekly_metrics_v=[], weekly_metric_rows_v=[], deviations_v=[])
    assert sync(app_factory, FakeReader(data)).status == "done"


def test_f08_fr10_a_status_that_changes_during_the_reads_means_publish_in_progress(
    app_factory: sessionmaker[Session],
) -> None:
    reader = FakeReader(published("run-B"))
    reader.status_run_ids = ["run-A", "run-B"]  # status read before the others, then again after
    failed = sync(app_factory, reader, run_id="run-B")
    assert failed.status == "failed"
    assert failed.error is not None
    assert "publish in progress" in failed.error
    assert count(app_factory, "mirror_batch_pipeline") == 0


def test_f08_fr05_no_published_data_fails_the_event_with_a_clear_error(
    app_factory: sessionmaker[Session],
) -> None:
    sync(app_factory, FakeReader(published("run-A")))
    reader = FakeReader(published("run-B"))
    reader.unavailable = True
    failed = sync(app_factory, reader, run_id="run-B")
    assert failed.status == "failed"
    assert failed.error is not None
    assert "no published data yet" in failed.error
    assert mirror_runs(app_factory) == {"run-A"}


def test_f08_fr05_a_published_object_missing_a_contract_column_fails_the_event(
    app_factory: sessionmaker[Session],
) -> None:
    data = published("run-A")
    del data["stage_reference_v"][0]["label"]
    failed = sync(app_factory, FakeReader(data), run_id="run-A")
    assert failed.status == "failed"
    assert failed.error is not None
    assert "stage_reference_v" in failed.error
    assert "label" in failed.error
    assert count(app_factory, "mirror_stage_reference") == 0


def test_f08_ac04_a_reclaimed_stale_event_is_completed_by_the_next_drain(
    app_factory: sessionmaker[Session],
) -> None:
    event_id = queue(app_factory, "run-A")
    with app_factory() as session:
        session.execute(
            text(
                "UPDATE sync_event SET status = 'claimed', claimed_at = now() - interval '6 minutes' WHERE id = :i"
            ),
            {"i": event_id},
        )
        session.commit()
    assert drain_once(app_factory, FakeReader(published("run-A"))) == 1
    done = event(app_factory, event_id)
    assert (done.status, done.error) == ("done", None)
    assert count(app_factory, "mirror_batch_pipeline") == 3


def test_f08_fr04_drain_processes_every_queued_event_then_stops(app_factory: sessionmaker[Session]) -> None:
    first, second = queue(app_factory, "run-A"), queue(app_factory, "run-A")
    assert drain_once(app_factory, FakeReader(published("run-A"))) == 2
    assert event(app_factory, first).rows_upserted == 22
    assert event(app_factory, second).rows_upserted == 0
    assert drain_once(app_factory, FakeReader(published("run-A"))) == 0
