"""T2: running a step: actions in order, progress lines, audit, one at a time, SSE with replay [F13-FR-03, FR-07, FR-08]."""

from collections.abc import Iterator

import pytest
from fakes import Harness
from fastapi import FastAPI
from fastapi.testclient import TestClient
from scenario.api import build_router, sse
from scenario.runner import Busy, PreconditionFailed, Run, UnknownStep

TOKEN = {"X-Scenario-Token": "s3cret"}


@pytest.fixture
def harness(monkeypatch: pytest.MonkeyPatch) -> Harness:
    monkeypatch.setenv("SCENARIO_TOKEN", "s3cret")
    return Harness(monkeypatch)


def messages(run: Run) -> list[str]:
    return [event["message"] for event in run.events]


def test_f13_fr01_actions_run_in_order_with_a_progress_line_each(harness: Harness) -> None:
    run = harness.run("lims-approve-B1042")
    assert run.status == "succeeded"
    kinds = [event["kind"] for event in run.events]
    assert kinds[0] == "start" and kinds[-1] == "done"
    assert kinds.count("action_start") == 4 and kinds.count("action_done") == 4
    lines = messages(run)
    assert lines.index("[1/4] LIMS: approve the sample") < lines.index("[3/4] Run the pipeline")
    assert lines.index("[3/4] Run the pipeline") < lines.index("[4/4] Wait for the app to sync")
    assert harness.world.paths()[:5] == [
        "GET app/api/overview", "GET lims/samples", "GET app/api/overview",
        "POST lims/events/approved", "POST erp/events/results-recorded",
    ]  # fmt: skip


def test_f13_fr01_variables_fill_the_event_body(harness: Harness) -> None:
    harness.run("lims-approve-B1042")
    approve = next(call for call in harness.world.calls if call[2] == "/events/approved")
    assert approve[3] == {"sample_id": "S-1"}


def test_f13_fr07_a_run_is_audited_as_scenario_step_by_the_actor(harness: Harness) -> None:
    harness.run("lims-approve-B1042", actor="admin")
    assert harness.audits == [
        (
            "admin",
            "scenario_step",
            {
                "step_id": "lims-approve-B1042",
                "outcome": "succeeded",
                "run_id": harness.registry.active.id,
                "message": "",
            },
        )  # type: ignore[union-attr]
    ]


def test_f13_fr07_the_cli_actor_is_system(harness: Harness) -> None:
    harness.run("run-pipeline", actor="system")
    assert harness.audits[0][0] == "system"


def test_f13_ac02_a_failed_precondition_names_the_problem_and_is_audited(harness: Harness) -> None:
    harness.world.rows["B1042"]["stage_key"] = "qa_release"
    with pytest.raises(PreconditionFailed) as error:
        harness.run("lims-approve-B1042")
    assert "already been approved in LIMS" in error.value.messages[0]
    assert harness.audits[0][1:2] == ("scenario_step",)
    assert harness.audits[0][2]["outcome"] == "precondition_failed"
    assert not any(call[2] == "/events/approved" for call in harness.world.calls)  # nothing was sent


def test_f13_fr01_a_refused_step_does_not_block_the_next(harness: Harness) -> None:
    harness.world.rows["B1042"]["stage_key"] = "qa_release"
    with pytest.raises(PreconditionFailed):
        harness.run("lims-approve-B1042")
    assert harness.run("run-pipeline").status == "succeeded"


def test_f13_fr01_an_unknown_step_is_refused(harness: Harness) -> None:
    with pytest.raises(UnknownStep):
        harness.run("no-such-step")


def test_f13_fr01_one_run_at_a_time(harness: Harness) -> None:
    harness.registry.begin("reset", "demo", "admin")  # a reset is running
    with pytest.raises(Busy, match="reset demo is running"):
        harness.run("run-pipeline")


def test_f13_fr01_a_service_error_fails_the_run_with_the_reason(harness: Harness) -> None:
    harness.world.fail["/events/approved"] = 409
    run = harness.run("lims-approve-B1042")
    assert run.status == "failed"
    assert "lims POST /events/approved answered 409: boom" in run.events[-1]["message"]
    assert harness.audits[0][2]["outcome"] == "failed"


def test_f13_fr08_wait_sync_times_out_naming_what_is_behind(harness: Harness) -> None:
    harness.world.synced = False
    harness.runner.sleep = lambda seconds: None
    run = harness.run("run-pipeline")
    assert run.status == "failed"
    assert (
        "did not sync run run-1 within 120 s; still behind: batch_pipeline_v, x" in run.events[-1]["message"]
    )


def test_f13_fr08_wait_sync_waits_for_the_run_started_in_the_same_step(harness: Harness) -> None:
    run = harness.run("run-pipeline")
    assert "the app has synced run run-1" in messages(run)[-2]
    assert harness.dagster.launched == ["r2r_pipeline"]


def test_f13_fr01_a_failed_pipeline_run_fails_the_step(harness: Harness) -> None:
    harness.dagster.final = "FAILURE"
    run = harness.run("run-pipeline")
    assert run.status == "failed" and "ended FAILURE" in run.events[-1]["message"]


def test_f13_fr02_advance_day_moves_the_clock_exactly_24_hours(harness: Harness) -> None:
    harness.run("advance-day")
    assert harness.advanced == [24]


def test_f13_fr02_the_agent_step_runs_as_alex_and_pull_forward_as_pat(harness: Harness) -> None:
    harness.run("airgap-agent")
    agent_call = next(call for call in harness.world.calls if call[2] == "/agents/air_gap/run")
    assert agent_call[4] == "alex"
    harness.run("pull-forward-B2077")
    put = next(call for call in harness.world.calls if call[1] == "PUT")
    assert put[2] == "/api/rows/RM1|B2077|100/need-by" and put[4] == "pat"
    assert put[3]["adjusted_date"] == "2026-11-26"


def test_f13_fr02_the_listing_shows_precondition_status(harness: Harness) -> None:
    harness.world.rows["B5003"]["air_gap"] = False
    listed = {step["id"]: step for step in harness.runner.listing()}
    assert listed["lims-approve-B1042"]["preconditions"] == "met"
    assert listed["ud-post-B5003"]["preconditions"] == "unmet"
    assert "no longer an air gap" in listed["ud-post-B5003"]["messages"][0]
    assert listed["advance-day"]["preconditions"] == "met"


# --- the stream and the API ------------------------------------------------------------------------


def finished_run() -> Run:
    run = Run(id="r1", kind="step", name="x", actor="admin")
    for number in range(3):
        run.emit("line", f"line {number}")
    run.finish("succeeded", "all done")
    return run


def frames(stream: Iterator[str]) -> list[str]:
    return [frame for frame in stream if not frame.startswith(":")]


def test_f13_fr03_the_stream_replays_everything_from_the_start() -> None:
    sent = frames(sse(finished_run(), after=0))
    assert len(sent) == 4
    assert sent[0].startswith("id: 0\ndata: ") and '"message": "all done"' in sent[-1]


def test_f13_fr03_a_late_subscriber_resumes_after_the_last_seq_it_saw() -> None:
    sent = frames(sse(finished_run(), after=2))
    assert [frame.split("\n")[0] for frame in sent] == ["id: 2", "id: 3"]


def test_f13_fr03_the_stream_waits_for_new_lines_and_ends_with_the_run() -> None:
    import threading

    run = Run(id="r1", kind="step", name="x", actor="admin")
    run.emit("line", "first")
    threading.Timer(0.1, lambda: run.finish("failed", "stopped")).start()
    sent = frames(sse(run, after=0, keepalive=5))
    assert [frame.split("\n")[0] for frame in sent] == ["id: 0", "id: 1"]


@pytest.fixture
def client(harness: Harness) -> TestClient:
    app = FastAPI()
    app.include_router(build_router(harness.runner, harness.registry))
    return TestClient(app)


def test_f13_fr03_every_route_needs_the_token(client: TestClient) -> None:
    assert client.get("/scenario/steps").status_code == 401
    assert client.post("/scenario/steps/run-pipeline/run").status_code == 401
    assert client.get("/scenario/runs/x/events").status_code == 401


def test_f13_fr03_steps_run_and_stream_over_http(client: TestClient) -> None:
    listed = client.get("/scenario/steps", headers=TOKEN).json()
    assert {s["id"] for s in listed} >= {"lims-approve-B1042", "airgap-agent"}
    started = client.post("/scenario/steps/run-pipeline/run", headers={**TOKEN, "X-Actor-User": "admin"})
    assert started.status_code == 202
    run_id = started.json()["run_id"]
    body = client.get(f"/scenario/runs/{run_id}/events", headers=TOKEN).text
    assert body.count("data: ") >= 5 and "run-pipeline finished" in body
    assert client.get(f"/scenario/runs/{run_id}", headers=TOKEN).json()["status"] == "succeeded"
    replay = client.get(f"/scenario/runs/{run_id}/events?after=3", headers=TOKEN).text
    assert replay.startswith("id: 3")


def test_f13_ac02_a_second_approval_is_a_409_with_a_clear_message(
    client: TestClient, harness: Harness
) -> None:
    harness.world.rows["B1042"]["stage_key"] = "qa_release"
    response = client.post("/scenario/steps/lims-approve-B1042/run", headers=TOKEN)
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["error"] == "precondition_failed" and "already been approved" in detail["message"]


def test_f13_fr03_unknown_step_and_unknown_run_are_404(client: TestClient) -> None:
    assert client.post("/scenario/steps/nope/run", headers=TOKEN).status_code == 404
    assert client.get("/scenario/runs/nope/events", headers=TOKEN).status_code == 404


def test_f13_fr03_a_run_while_another_is_active_is_a_409_busy(client: TestClient, harness: Harness) -> None:
    harness.registry.begin("reset", "demo", "admin")
    response = client.post("/scenario/steps/run-pipeline/run", headers=TOKEN)
    assert response.status_code == 409 and response.json()["detail"]["error"] == "busy"


def test_f14_fr11_b1042_results_are_recorded_in_the_erp_two_demo_hours_after_the_approval(
    harness: Harness,
) -> None:
    """OQ-166: the interface records the LIMS results, so B1042 can never become an air gap."""
    harness.run("lims-approve-B1042")
    recorded = next(call for call in harness.world.calls if call[2] == "/events/results-recorded")
    assert recorded[3] == {"prueflos": "100", "at": "2026-10-12T09:00:00+00:00"}  # NOW 07:00 + 2 h
    assert harness.advanced == []  # the clock did not move, so no replay key moves


def test_f14_fr13_the_b5003_steps_wait_for_a_decision_on_a_pending_proposal(harness: Harness) -> None:
    """OQ-168: an open B5003 proposal blocks the two steps that would remove the air gap under act 6."""
    harness.world.proposals = [{"row_key": "RM1|B5003|100", "status": "pending_approval"}]
    for step in ("ud-post-B5003", "interface-sync-B5003"):
        listed = {s["id"]: s for s in harness.runner.listing()}[step]
        assert listed["preconditions"] == "unmet" and "waiting for a decision" in listed["messages"][0]
        with pytest.raises(PreconditionFailed):
            harness.runner.start(step, "admin", wait=True)
    harness.world.proposals = [{"row_key": "RM1|B5003|100", "status": "executed"}]
    assert harness.run("ud-post-B5003").status == "succeeded"


def test_f14_fr13_the_listing_carries_the_groups_in_script_order(harness: Harness) -> None:
    listed = harness.runner.listing()
    groups = [step["group"] for step in listed]
    order = ["Act 3", "Act 5", "Act 6", "After act 6", "Extras"]
    assert sorted(set(groups), key=order.index) == order
    assert groups == sorted(groups, key=order.index)  # never out of order
    by_id = {step["id"]: step["group"] for step in listed}
    assert by_id["ud-post-B5003"] == by_id["interface-sync-B5003"] == "After act 6"


def test_f14_fr14_pull_forward_is_refused_when_b2077_is_already_adjusted_and_writes_nothing(
    harness: Harness,
) -> None:
    """OQ-169: the act 5 fallback is safe to press twice."""
    harness.world.rows["B2077"]["adjusted_need_by_date"] = "2026-11-26"
    listed = {s["id"]: s for s in harness.runner.listing()}["pull-forward-B2077"]
    assert listed["preconditions"] == "unmet" and "already adjusted" in listed["messages"][0]
    with pytest.raises(PreconditionFailed):
        harness.runner.start("pull-forward-B2077", "admin", wait=True)
    assert not [call for call in harness.world.calls if call[1] == "PUT"]  # nothing written


def test_f14_fr12_a_run_with_one_missing_recording_still_succeeds_and_names_it(harness: Harness) -> None:
    harness.world.agent_answer = {
        "created": [{}, {}, {}],
        "skipped": [],
        "errors": [{"message": "No recording for B1042: record it or run live"}],
    }
    run = harness.run("airgap-agent")
    assert run.status == "succeeded"
    assert any("3 proposal(s) created" in m and "No recording for B1042" in m for m in messages(run))
    harness.world.agent_answer = {"created": [], "skipped": [], "errors": [{"message": "No recording for B1042: x"}]}
    assert harness.run("airgap-agent").status == "failed"
