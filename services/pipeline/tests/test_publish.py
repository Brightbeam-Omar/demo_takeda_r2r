"""T4: publish all objects, reference objects from the profile (F07-FR-03, F07-AC-01, F07-AC-05)."""

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest
from fixture_world import World
from r2r_core.profile import SiteProfile
from r2r_pipeline.context import RunContext
from r2r_pipeline.lake import delta_exists, read_delta
from r2r_pipeline.publish import PUBLISH_ORDER, publish
from r2r_pipeline.runlog import StepResult, run_step, step_row
from r2r_pipeline.setup import setup
from r2r_pipeline.snapshot import snapshot_aggregate
from r2r_pipeline.transform import transform

D = date
FRESHNESS = {
    "erp": {"max_updated_at": "2026-10-12T06:00:00+00:00", "extracted_at": "2026-10-12T07:00:00+00:00"}
}


def run_all(world: World, lake: Path, profile: SiteProfile, run_id: str = "run-1") -> RunContext:
    """Setup, a stand-in for extract (the world is written as staging), transform, snapshot and publish."""
    ctx = setup(profile, lake, run_id=run_id)
    world.write(lake)
    run_step(ctx, "extract", lambda: StepResult(detail={"freshness": FRESHNESS}))
    run_step(ctx, "transform", lambda: (transform(ctx), StepResult())[1])
    run_step(ctx, "snapshot_aggregate", lambda: snapshot_aggregate(ctx))
    run_step(ctx, "publish", lambda: publish(ctx))
    return ctx


def table(lake: Path, name: str) -> list[dict[str, Any]]:
    return read_delta(lake, f"published.{name}").to_pylist()


@pytest.fixture
def world() -> World:
    w = World()
    w.receive("B1", "10000001", D(2026, 10, 1))
    w.receive("B2", "10000002", D(2026, 9, 1))
    w.demand(1, D(2026, 11, 20))
    w.deviation("DEV-000001", "open", [("RM1", "B1"), ("RM1", "B2")])
    return w


@pytest.mark.usefixtures("demo_clock")
def test_f07_ac01_all_published_objects_exist_and_the_status_has_one_row(
    world: World, tmp_path: Path, profile: SiteProfile
) -> None:
    ctx = run_all(world, tmp_path, profile)
    assert PUBLISH_ORDER == (
        "batch_pipeline_v", "weekly_metrics_v", "weekly_metric_rows_v", "stage_reference_v",
        "metric_reference_v", "reason_codes_v", "deviations_v", "expected_deliveries_v", "inbound_checks_v",
        "change_controls_v", "pipeline_status_v",
    )  # fmt: skip
    assert all(delta_exists(tmp_path, f"published.{name}") for name in PUBLISH_ORDER)
    [status] = table(tmp_path, "pipeline_status_v")
    assert status["last_run_id"] == ctx.run_id == "run-1"
    assert status["row_count"] == 2
    assert json.loads(status["source_freshness_json"]) == FRESHNESS
    assert status["started_at"] == datetime(2026, 10, 12, 7, 0, tzinfo=UTC)
    assert status["last_success_at"] == datetime(2026, 10, 12, 7, 0, tzinfo=UTC)


@pytest.mark.usefixtures("demo_clock")
def test_f07_fr03_the_status_keeps_one_row_after_a_second_run(
    world: World, tmp_path: Path, profile: SiteProfile
) -> None:
    run_all(world, tmp_path, profile, "run-1")
    run_all(world, tmp_path, profile, "run-2")
    [status] = table(tmp_path, "pipeline_status_v")
    assert status["last_run_id"] == "run-2"
    assert {r["run_id"] for r in table(tmp_path, "batch_pipeline_v")} == {"run-2"}


@pytest.mark.usefixtures("demo_clock")
def test_f07_fr03_batch_pipeline_has_the_contract_columns_and_the_run_columns(
    world: World, tmp_path: Path, profile: SiteProfile
) -> None:
    run_all(world, tmp_path, profile)
    rows = table(tmp_path, "batch_pipeline_v")
    assert len(rows) == 2
    row = rows[0]
    for column in (
        "row_key", "material_no", "erp_results_recorded_at", "stage_key", "stage_rule_id", "cycle_start_date", "ud_effective", "stage_sort",
        "current_stage_entry_date", "lims_rejected", "receipt_entry", "qa_release_exit", "applicable_sla_json",
        "system_need_by_locked", "on_hold", "erp_blocked", "re_eval", "offsite", "full_spec", "ud_rejected",
        "deviation_light", "inbound_light", "snapshot_date", "run_id", "published_at",
    ):  # fmt: skip
        assert column in row, column
    assert row["snapshot_date"] == D(2026, 10, 12)
    assert row["published_at"] == datetime(2026, 10, 12, 7, 0, tzinfo=UTC)
    assert row["system_need_by_locked"] == D(2026, 11, 20)
    assert json.loads(row["source_refs_json"])["erp"]["mcha"].startswith("RM1|")


@pytest.mark.usefixtures("demo_clock")
def test_f07_fr03_weekly_objects_are_copies_of_the_intelligence_tables(
    world: World, tmp_path: Path, profile: SiteProfile
) -> None:
    run_all(world, tmp_path, profile)
    published = read_delta(tmp_path, "published.weekly_metrics_v")
    assert published.schema.names == ["metric_id", "week_start", "completed", "on_time", "pct", "run_id"]
    assert published.to_pylist() == read_delta(tmp_path, "intelligence.weekly_metrics").to_pylist()
    rows = read_delta(tmp_path, "published.weekly_metric_rows_v")
    assert rows.schema.names == [
        "metric_id", "week_start", "row_key", "entry_date", "exit_date", "duration_days", "sla_days",
        "on_time", "run_id",
    ]  # fmt: skip


@pytest.mark.usefixtures("demo_clock")
def test_f07_ac05_app_side_metrics_are_awaiting_signal_with_a_reason(
    world: World, tmp_path: Path, profile: SiteProfile
) -> None:
    run_all(world, tmp_path, profile)
    reference = {r["metric_id"]: r for r in table(tmp_path, "metric_reference_v")}
    assert list(reference) == ["M1", "M2", "M3", "M4", "M5", "M6", "M7"]
    for metric in ("M1", "M2", "M4", "M5"):
        assert reference[metric]["status"] == "awaiting_signal"
        assert reference[metric]["computed_in"] == "app"
        assert reference[metric]["null_reason"]
    for metric in ("M3", "M6", "M7"):
        assert (reference[metric]["status"], reference[metric]["null_reason"]) == ("active", None)
    assert (reference["M3"]["stage_key"], reference["M3"]["sla_days"]) == ("sampling", 7)
    assert (reference["M5"]["stage_key"], reference["M5"]["sla_days"]) == (None, 30)


@pytest.mark.usefixtures("demo_clock")
def test_f07_fr03_stage_and_reason_references_come_from_the_profile(
    world: World, tmp_path: Path, profile: SiteProfile
) -> None:
    run_all(world, tmp_path, profile)
    stages = table(tmp_path, "stage_reference_v")
    assert [s["stage_key"] for s in stages] == [s.key for s in profile.stages]
    assert [s["sort"] for s in stages] == list(range(1, len(stages) + 1))
    by_key = {s["stage_key"]: s for s in stages}
    assert (by_key["qc_testing"]["sla_days"], by_key["qc_testing"]["reeval_sla_days"]) == (42, 27)
    assert by_key["receipt"]["reeval_sla_days"] is None
    assert by_key["released"]["terminal"] is True
    assert (by_key["sampling"]["team"], by_key["sampling"]["action"]) == (
        "Manufacturing",
        "Collect QC sample",
    )
    reasons = table(tmp_path, "reason_codes_v")
    assert [(r["code"], r["label"]) for r in reasons] == [(r.code, r.label) for r in profile.reason_codes]
    assert reasons[0] == {"code": "CAMPAIGN_PULLED_FORWARD", "label": "Campaign pulled forward"}


@pytest.mark.usefixtures("demo_clock")
def test_f07_fr03_deviations_has_one_row_per_linked_batch(
    world: World, tmp_path: Path, profile: SiteProfile
) -> None:
    run_all(world, tmp_path, profile)
    rows = table(tmp_path, "deviations_v")
    assert [(r["deviation_no"], r["batch_no"], r["severity"], r["status"]) for r in rows] == [
        ("DEV-000001", "B1", "minor", "open"),
        ("DEV-000001", "B2", "minor", "open"),
    ]


@pytest.mark.usefixtures("demo_clock")
def test_f19_fr03_deviations_carry_the_new_fields_and_the_run_id(
    tmp_path: Path, profile: SiteProfile
) -> None:
    world = World()
    world.receive("B1", "10000001", D(2026, 10, 1))
    world.demand(1, D(2026, 11, 20))
    world.deviation(
        "DEV-000001",
        "closed",
        [("RM1", "B1")],
        severity="moderate",
        causal_factor="Carrier handling",
        investigation_summary="Handled with the carrier.",
    )
    run_all(world, tmp_path, profile)
    [row] = table(tmp_path, "deviations_v")
    assert (row["severity"], row["causal_factor"], row["investigation_summary"]) == (
        "moderate",
        "Carrier handling",
        "Handled with the carrier.",
    )
    assert (row["description"], row["run_id"]) == ("d", "run-1")
    assert read_delta(tmp_path, "published.deviations_v").schema.names == [
        "deviation_no", "material_no", "batch_no", "title", "severity", "status", "opened_on", "closed_on",
        "root_cause_category", "causal_factor", "investigation_summary", "description", "owner", "run_id",
    ]  # fmt: skip


@pytest.mark.usefixtures("demo_clock")
def test_f19_fr03_change_controls_has_one_row_per_linked_batch(tmp_path: Path, profile: SiteProfile) -> None:
    world = World()
    world.receive("B1", "10000001", D(2026, 10, 1))
    world.receive("B2", "10000002", D(2026, 10, 1))
    world.demand(1, D(2026, 11, 20))
    world.change_control("CC-000002", "approved", [("RM1", "B1"), ("RM1", "B2")], D(2026, 11, 1))
    world.change_control("CC-000001", "open", [("RM1", "B1")])
    run_all(world, tmp_path, profile)
    rows = table(tmp_path, "change_controls_v")
    assert [(r["cc_no"], r["batch_no"], r["status"], r["effective_on"], r["run_id"]) for r in rows] == [
        ("CC-000001", "B1", "open", None, "run-1"),
        ("CC-000002", "B1", "approved", D(2026, 11, 1), "run-1"),
        ("CC-000002", "B2", "approved", D(2026, 11, 1), "run-1"),
    ]
    assert read_delta(tmp_path, "published.change_controls_v").schema.names == [
        "cc_no", "material_no", "batch_no", "title", "status", "current_state", "proposed_state", "opened_on",
        "effective_on", "run_id",
    ]  # fmt: skip


@pytest.mark.usefixtures("demo_clock")
def test_f07_fr03_publish_refuses_a_run_that_did_not_build_its_snapshot(
    world: World, tmp_path: Path, profile: SiteProfile
) -> None:
    ctx = setup(profile, tmp_path, run_id="run-1")
    world.write(tmp_path)
    with pytest.raises(LookupError, match="transform"):
        publish(ctx)
    assert not delta_exists(tmp_path, "published.pipeline_status_v")


@pytest.mark.usefixtures("demo_clock")
def test_f07_oq046_the_status_takes_freshness_and_start_from_the_run_log(
    world: World, tmp_path: Path, profile: SiteProfile
) -> None:
    run_all(world, tmp_path, profile)
    [status] = table(tmp_path, "pipeline_status_v")
    assert json.loads(status["source_freshness_json"]) == FRESHNESS  # the extract row's detail_json
    assert status["started_at"] == step_row(_ctx(profile, tmp_path), "setup")["started_at"]


@pytest.mark.usefixtures("demo_clock")
def test_f07_fr03_published_column_types_follow_the_contract(
    world: World, tmp_path: Path, profile: SiteProfile
) -> None:
    import pyarrow as pa

    run_all(world, tmp_path, profile)
    assert read_delta(tmp_path, "published.weekly_metrics_v").schema.field("pct").type == pa.decimal128(5, 1)
    for name in ("stage_reference_v", "metric_reference_v", "reason_codes_v"):
        assert "run_id" not in read_delta(tmp_path, f"published.{name}").schema.names, name


@pytest.mark.usefixtures("demo_clock")
def test_f07_oq047_a_crash_inside_publish_leaves_the_status_unwritten(
    world: World, tmp_path: Path, profile: SiteProfile, monkeypatch: pytest.MonkeyPatch
) -> None:
    import r2r_pipeline.publish as module

    run_all(world, tmp_path, profile, "run-1")
    real = module.write_delta

    def crash_on_deviations(root: Path, name: str, data: object, mode: str = "overwrite") -> None:
        if name.endswith("deviations_v"):
            raise OSError("disk full")
        real(root, name, data, mode)

    monkeypatch.setattr(module, "write_delta", crash_on_deviations)
    with pytest.raises(OSError, match="disk full"):
        run_all(world, tmp_path, profile, "run-2")
    assert table(tmp_path, "pipeline_status_v")[0]["last_run_id"] == "run-1"  # still the previous run
    assert {r["run_id"] for r in table(tmp_path, "batch_pipeline_v")} == {
        "run-2"
    }  # the mix a reader can detect


def _ctx(profile: SiteProfile, lake: Path) -> RunContext:
    from r2r_pipeline.context import new_context

    return new_context(profile, lake, run_id="run-1")


@pytest.mark.usefixtures("demo_clock")
def test_f19_fr02_inbound_checks_has_one_row_per_lot_with_a_check_and_its_items(
    tmp_path: Path, profile: SiteProfile
) -> None:
    world = World()
    world.receive("B1", "10000001", D(2026, 10, 1))
    world.check("10000001", "resolved", D(2026, 10, 3))
    world.items(
        "10000001",
        [
            ("PHYS", "Physical evaluation", "PASS"),
            ("QTYR", "Quantity received verification", "FAIL"),
            ("RESL", "Results of analytical work", "COMP"),
        ],
    )
    world.receive("B2", "10000002", D(2026, 10, 2))  # open check, no items
    world.receive("B3", "10000003", D(2026, 10, 2))
    world.reeval("B3", "10000004", D(2026, 10, 9))  # a 09 lot with no check: no row
    world.demand(1, D(2026, 11, 20))
    run_all(world, tmp_path, profile)
    rows = {r["prueflos"]: r for r in table(tmp_path, "inbound_checks_v")}
    assert set(rows) == {"10000001", "10000002", "10000003"}
    resolved = rows["10000001"]
    assert resolved["row_key"] == "RM1|B1|10000001"
    assert (resolved["status"], resolved["failed_count"], resolved["run_id"]) == ("resolved", 1, "run-1")
    assert resolved["deadline"] == D(2026, 10, 11)  # cycle start 1 Oct + the 10-day receipt SLA
    assert json.loads(resolved["items_json"]) == [
        {"seq": 1, "check_code": "PHYS", "check_label": "Physical evaluation", "outcome": "PASS"},
        {"seq": 2, "check_code": "QTYR", "check_label": "Quantity received verification", "outcome": "FAIL"},
        {"seq": 3, "check_code": "RESL", "check_label": "Results of analytical work", "outcome": "COMP"},
    ]
    assert (rows["10000002"]["status"], rows["10000002"]["failed_count"], rows["10000002"]["items_json"]) == (
        "open",
        0,
        "[]",
    )
    assert read_delta(tmp_path, "published.inbound_checks_v").schema.names == [
        "row_key", "prueflos", "status", "deadline", "failed_count", "items_json", "run_id",
    ]  # fmt: skip


@pytest.mark.usefixtures("demo_clock")
def test_f19_fr02_a_re_evaluation_deadline_uses_its_own_cycle_start(
    tmp_path: Path, profile: SiteProfile
) -> None:
    world = World()
    world.receive("B1", "10000001", D(2026, 9, 1))
    world.reeval("B1", "10000002", D(2026, 10, 8))
    world.add("stg_zinbchk", prueflos="10000002", status="open")
    world.demand(1, D(2026, 11, 20))
    run_all(world, tmp_path, profile)
    rows = {r["prueflos"]: r for r in table(tmp_path, "inbound_checks_v")}
    assert rows["10000002"]["deadline"] == D(2026, 10, 18)
