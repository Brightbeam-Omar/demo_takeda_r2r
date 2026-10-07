"""Test doubles shared by the agents tests."""

import json
from typing import Any

import httpx
from agents.air_gap.schema import AirGapTicket, EvidenceItem
from agents.gateway.base import Block, ModelGateway, ModelResult, ToolUseBlock

USERS = {
    "pat": ("Pat", "planner"),
    "quinn": ("Quinn", "qc_lead"),
    "alex": ("Alex", "qa_release"),
    "sam": ("Sam", "viewer"),
    "admin": ("Admin", "admin"),
}


def fake_app_api() -> httpx.Client:
    """An app-api stand-in that answers ``/api/me`` like the real one (default persona: pat)."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path != "/api/me":
            return httpx.Response(404)
        key = request.headers.get("X-Demo-User", "pat")
        if key not in USERS:
            return httpx.Response(401, json={"detail": "unknown X-Demo-User"})
        name, role = USERS[key]
        return httpx.Response(200, content=json.dumps({"user_key": key, "display_name": name, "role": role}))

    return httpx.Client(base_url="http://app-api.test", transport=httpx.MockTransport(handler))


class ListTrace:
    """An in-memory trace sink for tests that do not need the database."""

    def __init__(self, trace_id: str = "TR-0001") -> None:
        self.trace_id = trace_id
        self.steps: list[dict[str, object]] = []

    def step(
        self,
        step_type: str,
        payload: object,
        *,
        tokens_in: int | None = None,
        tokens_out: int | None = None,
        latency_ms: int | None = None,
    ) -> int:
        self.steps.append(
            {
                "step_type": step_type,
                "payload": payload,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "latency_ms": latency_ms,
            }
        )
        return len(self.steps)


ROW_KEY = "RM10067|B5003|10000459"
INSIGHTS_ROW: dict[str, object] = {
    "row_key": ROW_KEY,
    "batch_no": "B5003",
    "material_no": "RM10067",
    "material_desc": "API Intermediate 009",
    "stage_key": "qa_release",
    "stage_label": "QA Release",
    "air_gap_hours": 30,
    "days_gap": 1,
}


def row_body(**changes: object) -> dict[str, object]:
    """An ``/api/rows/{row_key}`` answer for B5003 (the demo-start air gap), with the volatile fields present."""
    body: dict[str, object] = {
        "row_key": ROW_KEY,
        "material_no": "RM10067",
        "material_desc": "API Intermediate 009",
        "batch_no": "B5003",
        "supplier_name": "Supplier 030",
        "campaign": "CMP-ALPHA",
        "stage_key": "qa_release",
        "inspection_lot_no": "10000459",
        "lims_status": "approved",
        "ud_code": None,
        "operative_need_by": "2026-10-22",
        "air_gap": True,
        "air_gap_hours": 30,
        "late": False,
        "plan": {"rag": "green", "days_remaining": 10},
        "latest_status": {"comment": "free text that must not reach the model", "at": "x"},
        "freshness": {"contract_run_id": "run-1", "last_success_at": "t", "freshness_minutes": 0},
        "facts": {
            "sample_id": "S-0000404",
            "lims_approved_at": "2026-10-11T01:00:00Z",
            "erp_results_recorded_at": None,
            "open_deviation_count": 0,
            "mirrored_at": "2026-10-06T14:04:50Z",
            "contract_run_id": "run-1",
        },
    }
    body.update(changes)
    return body


def source_transport(
    *, row: dict[str, object] | None = None, ud_code: str | None = None, results_recorded: str | None = None,
    deviations: list[dict[str, object]] | None = None, volatile: str = "a",
    insights: list[dict[str, object]] | None = None,
) -> httpx.MockTransport:  # fmt: skip
    """The app, LIMS, ERP and QMS behind one mock transport (B5003). ``volatile`` changes only meaningless fields."""

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method != "GET":
            raise AssertionError(f"a tool made a {request.method} request to {request.url}")
        if path == "/api/rows/" + "RM10067%7CB5003%7C10000459" or path == f"/api/rows/{ROW_KEY}":
            body = dict(row or row_body())
            body["freshness"] = {"contract_run_id": f"run-{volatile}", "last_success_at": volatile}
            return httpx.Response(200, json=body)
        if path == "/api/overview/insights":
            rows = insights if insights is not None else [INSIGHTS_ROW]
            return httpx.Response(200, json={"total": len(rows), "rows": rows})
        if path == "/samples/S-0000404":
            return httpx.Response(
                200,
                json={
                    "sample_id": "S-0000404",
                    "inspection_lot_no": "10000459",
                    "material_no": "RM10067",
                    "batch_no": "B5003",
                    "collected_date": "2026-08-25",
                    "offsite_test": False,
                    "external_lab": None,
                    "shipped_date": None,
                    "status": "approved",
                    "approved_at": "2026-10-11T01:00:00Z",
                    "updated_at": f"2026-10-11T01:00:0{1 if volatile == 'b' else 0}Z",
                },
            )
        if path == "/samples/S-0000404/results":
            return httpx.Response(200, json=[])
        if path == "/lots/10000459":
            return httpx.Response(
                200,
                json={
                    "lot": {
                        "prueflos": "10000459",
                        "art": "01",
                        "matnr": "RM10067",
                        "charg": "B5003",
                        "pastrterm": "2026-08-18",
                        "vcode": ud_code,
                        "vdatum": None,
                        "zresrec": results_recorded,
                        "updated_at": volatile,
                    },
                    "inbound_check": {"status": "passed", "updated_at": volatile},
                    "inbound_items": [],
                },
            )
        if path == "/deviations" and request.url.params.get("batch_no") == "B5003":
            return httpx.Response(200, json=deviations or [])
        if path.startswith("/deviations/"):
            for deviation in deviations or []:
                if path.endswith(str(deviation["deviation_no"])):
                    return httpx.Response(200, json=deviation)
        return httpx.Response(404, json={"detail": "unknown"})

    return httpx.MockTransport(handler)


OPEN_DEVIATION = {
    "deviation_no": "DEV-000039", "title": "Temperature excursion in storage", "severity": "minor",
    "status": "open", "opened_on": "2026-09-01", "closed_on": None,
}  # fmt: skip


def evidence() -> list[EvidenceItem]:
    return [
        EvidenceItem(system="LIMS", ref="S-0000404", field="approved_at", value="2026-10-11T01:00:00Z"),
        EvidenceItem(system="ERP", ref="10000459", field="results_recorded_at", value="none"),
        EvidenceItem(system="ERP", ref="10000459", field="ud_code", value="none"),
    ]


def ticket(**changes: Any) -> AirGapTicket:
    data: dict[str, Any] = {
        "row_key": ROW_KEY,
        "title": "Batch B5003: LIMS approved, no ERP usage decision",
        "summary": "LIMS approved sample S-0000404 for batch B5003 30 hours ago. The ERP has no usage decision "
        "and no results record for lot 10000459. Post the usage decision.",
        "evidence": evidence(),
        "hours_in_gap": 30,
        "open_deviations": [],
        "recommended_action": "post_usage_decision",
        "priority": "high",
        "recipient_role": "qa_release",
    }
    data.update(changes)
    return AirGapTicket.model_validate(data)


class B5003Model(ModelGateway):
    """A model that investigates B5003 the way the prompt says: four reads, then one submission."""

    provider = "scripted"
    model_id = "scripted-model"

    def __init__(self, **ticket_changes: Any) -> None:
        self.ticket_changes = ticket_changes
        self.calls = 0

    def generate(self, *, system, messages, tools, turn, agent_key, prompt_version) -> ModelResult:  # type: ignore[no-untyped-def]
        self.calls += 1
        plan: dict[int, list[Block]] = {
            1: [ToolUseBlock(id="toolu_1", name="get_row", input={"row_key": ROW_KEY})],
            2: [
                ToolUseBlock(id="toolu_2", name="get_lims_sample", input={"sample_id": "S-0000404"}),
                ToolUseBlock(id="toolu_3", name="get_erp_lot", input={"prueflos": "10000459"}),
            ],
            3: [ToolUseBlock(id="toolu_4", name="list_deviations", input={"batch_no": "B5003"})],
            4: [
                ToolUseBlock(
                    id="toolu_5",
                    name="submit_ticket",
                    input=ticket(**self.ticket_changes).model_dump(mode="json"),
                )
            ],
        }
        return ModelResult(
            content=plan[turn], stop_reason="tool_use", tokens_in=1000 * turn, tokens_out=100,
            latency_ms=50, model_id="scripted-model",
        )  # fmt: skip
