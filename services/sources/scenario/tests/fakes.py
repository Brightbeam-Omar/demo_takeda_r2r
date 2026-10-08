"""A fake of every service a step talks to, behind one ``httpx`` mock transport (no network, no database)."""

import json
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from scenario import runner as runner_module
from scenario.gateway import Endpoints, Gateway
from scenario.runner import Run, Runner, RunRegistry
from scenario.steps import load_steps

NOW = datetime(2026, 10, 12, 7, 0, tzinfo=UTC)

ENDPOINTS = Endpoints(
    app="http://app.test", erp="http://erp.test", lims="http://lims.test", qms="http://qms.test",
    agents="http://agents.test",
)  # fmt: skip


def row(batch: str, stage: str, **extra: Any) -> dict[str, Any]:
    return {
        "row_key": f"RM1|{batch}|100",
        "batch_no": batch,
        "material_no": "RM1",
        "inspection_lot_no": "100",
        "lot_type": "01",
        "stage_key": stage,
        "air_gap": False,
        "adjusted_need_by_date": None,
        **extra,
    }


class World:
    """Records every call; answers like the services do. ``rows`` is what the app shows."""

    def __init__(self) -> None:
        self.rows = {
            "B1042": row("B1042", "qc_testing"),
            "B5003": row("B5003", "qa_release", air_gap=True),
            "B2077": row("B2077", "sampling"),
            "B3150": row("B3150", "qa_release"),
        }
        self.calls: list[tuple[str, str, str, Any, str | None]] = []
        self.run_id = "run-1"
        self.follow: FakeDagster | None = (
            None  # when set, the app has synced whatever pipeline run Dagster started last
        )
        self.synced = True  # False: the watermarks stay on an older run, so wait_sync times out
        self.deviations = {"B3150": [{"deviation_no": "DEV-1", "closed_on": None}], "B1042": []}
        self.proposals: list[dict[str, Any]] = []  # what GET /proposals lists
        self.agent_answer: dict[str, Any] = {"created": [{}, {}, {}, {}], "skipped": [], "errors": []}
        self.fail: dict[str, int] = {}  # path -> HTTP status to answer with
        self.timeline: list[str] = []  # what happened, in order (shared with the other fakes of a test)

    def __call__(self, request: httpx.Request) -> httpx.Response:
        host, path = request.url.host, request.url.path
        body = json.loads(request.content) if request.content else None
        user = request.headers.get("X-Demo-User")
        self.calls.append((host, request.method, path, body, user))
        self.timeline.append(f"{request.method} {path}")
        if path in self.fail:
            return httpx.Response(self.fail[path], json={"detail": "boom"})
        if path == "/api/overview":
            batch = request.url.params.get("q")
            if batch is None:  # the health summary asks for everything
                rows = list(self.rows.values())
                return httpx.Response(200, json={"rows": rows, "batch_count": len(rows)})
            return httpx.Response(200, json={"rows": [self.rows[batch]] if batch in self.rows else []})
        if path == "/proposals":
            return httpx.Response(200, json={"counts": {}, "rows": self.proposals})
        if path == "/api/sync/status":
            latest = self.follow.launched_ids[-1] if self.follow and self.follow.launched_ids else self.run_id
            at = latest if self.synced else "older"
            marks = [{"object_name": "batch_pipeline_v", "run_id": at}, {"object_name": "x", "run_id": at}]
            return httpx.Response(200, json={"watermarks": marks, "events": [{"status": "done"}]})
        if path == "/samples":
            return httpx.Response(200, json=[{"sample_id": "S-1", "status": "in_progress"}])
        if path == "/deviations":
            return httpx.Response(200, json=self.deviations.get(request.url.params["batch_no"], []))
        if path == "/agents/air_gap/run":
            return httpx.Response(200, json=self.agent_answer)
        return httpx.Response(200, json={"ok": True})

    def gateway(self) -> Gateway:
        return Gateway(ENDPOINTS, token="t", transport=httpx.MockTransport(self))

    def paths(self) -> list[str]:
        return [f"{method} {host.split('.')[0]}{path}" for host, method, path, *_ in self.calls]


class FakeDagster:
    """Stands in for ``DagsterClient``: every launch succeeds after ``polls`` status checks (or ends as given)."""

    def __init__(self, final: str = "SUCCESS", polls: int = 1, timeline: list[str] | None = None) -> None:
        self.final = final
        self.polls = polls
        self.launched: list[str] = []
        self.launched_ids: list[str] = []
        self.timeline = timeline if timeline is not None else []

    def launch(self, job_name: str = "r2r_pipeline") -> str:
        self.launched.append(job_name)
        self.timeline.append(f"dagster {job_name}")
        self.launched_ids.append(f"run-{len(self.launched)}")
        return self.launched_ids[-1]

    def status(self, run_id: str) -> str:
        self.polls -= 1
        return "STARTED" if self.polls > 0 else self.final


class Harness:
    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.world = World()
        self.dagster = FakeDagster()
        self.audits: list[tuple[str, str, dict[str, Any]]] = []
        self.advanced: list[int] = []
        monkeypatch.setattr(
            runner_module,
            "write_audit",
            lambda engine, at, actor, action, details: self.audits.append((actor, action, details)),
        )
        monkeypatch.setattr(
            runner_module, "advance_hours", lambda engine, hours: self.advanced.append(hours) or NOW
        )
        self.registry = RunRegistry()
        self.runner = Runner(
            load_steps(),
            self.world.gateway(),
            None,
            lambda: self.dagster,
            self.registry,
            lambda: NOW,
            sleep=lambda s: None,  # type: ignore[arg-type]
        )

    def run(self, step_id: str, actor: str = "admin") -> Run:
        return self.runner.start(step_id, actor, wait=True)
