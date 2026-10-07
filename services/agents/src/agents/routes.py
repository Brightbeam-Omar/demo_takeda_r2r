"""The agents HTTP API (F12-FR-08). The frontend calls it as ``/agents-api/...``; the proxy strips the prefix.

Reads are open to every role. Running needs ``qa_release`` or ``admin``; approving and rejecting need the
proposal's ``required_role`` or ``admin`` (and a refused write leaves a ``forbidden`` audit row).
"""

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from r2r_core.web import require_scenario_token
from sqlalchemy import func, select

from agents.air_gap import agent as air_gap_agent
from agents.air_gap.candidates import AGENT_KEY
from agents.air_gap.replay_check import replay_check
from agents.auth import Principal, current_principal, forbid, require_role
from agents.db import agent_trace, proposal
from agents.deps import Deps
from agents.gateway.replay import recorded_model_id
from agents.harness import proposals
from agents.harness.proposals import ProposalError

router = APIRouter()
autorun_router = APIRouter(prefix="/agents/autorun", dependencies=[Depends(require_scenario_token)])


def deps_of(request: Request) -> Deps:
    deps: Deps = request.app.state.deps
    return deps


DepsDep = Annotated[Deps, Depends(deps_of)]
PrincipalDep = Annotated[Principal, Depends(current_principal)]
RunnerDep = Annotated[Principal, Depends(require_role("qa_release", "admin"))]


class AgentCard(BaseModel):
    key: str
    name: str
    purpose: str
    provider: str
    model_id: str
    prompt_version: str
    tools: list[str]
    can_run: bool
    last_run_at: datetime | None
    proposals_total: int


class RunBody(BaseModel):
    row_key: str | None = None


class RunResultOut(BaseModel):
    row_key: str
    outcome: str
    proposal_id: int | None
    status: str | None
    trace_id: str | None
    message: str
    replay_miss: dict[str, str] | None


class RunOut(BaseModel):
    created: list[RunResultOut]
    skipped: list[RunResultOut]
    errors: list[RunResultOut]


class RejectBody(BaseModel):
    reason: str = Field(max_length=2000)


@router.get("/agents")
def list_agents(deps: DepsDep, principal: PrincipalDep) -> list[AgentCard]:
    with deps.engine.connect() as connection:
        last = connection.execute(
            select(func.max(agent_trace.c.at)).where(agent_trace.c.step_type == "input")
        ).scalar_one()
        total = connection.execute(select(func.count()).select_from(proposal)).scalar_one()
    model = deps.settings.model_id
    if deps.gateway.provider == "replay":
        model = recorded_model_id(deps.settings.recordings_dir, AGENT_KEY) or model
    return [
        AgentCard(
            key=AGENT_KEY,
            name=air_gap_agent.NAME,
            purpose=air_gap_agent.PURPOSE,
            provider=deps.gateway.provider,
            model_id=model,
            prompt_version=air_gap_agent.PROMPT_VERSION,
            tools=air_gap_agent.build_spec(deps.http).tools.names(),
            can_run=principal.role in ("qa_release", "admin"),
            last_run_at=last,
            proposals_total=int(total),
        )
    ]


@router.post("/agents/air_gap/run")
def run_air_gap(deps: DepsDep, principal: RunnerDep, body: RunBody | None = None) -> RunOut:
    summary = air_gap_agent.run(deps, principal, row_key=body.row_key if body else None)
    out = RunOut(
        created=[_result(r) for r in summary.of("created")],
        skipped=[_result(r) for r in summary.of("skipped")],
        errors=[_result(r) for r in summary.of("error")],
    )
    if out.errors and not out.created:
        first = out.errors[0]
        raise HTTPException(
            status_code=409,
            detail={
                "error": "replay_miss" if first.replay_miss else "run_failed",
                "message": first.message,
                "replay_miss": first.replay_miss,
                "errors": [e.model_dump() for e in out.errors],
            },
        )
    return out


class CandidateReplayOut(BaseModel):
    batch_no: str
    air_gap_hours: int
    replays: bool
    missing_key: str | None
    message: str


class ReplayCheckOut(BaseModel):
    recordings_dir: str
    recording_files: int
    demo_start: bool
    candidates: list[CandidateReplayOut]


@router.get("/agents/air_gap/replay-check")
def air_gap_replay_check(deps: DepsDep, principal: PrincipalDep) -> ReplayCheckOut:
    """Would the air-gap agent replay for every current candidate? Writes nothing (F14-FR-05, OQ-160)."""
    result = replay_check(deps.http, deps.profile, deps.settings.recordings_dir, principal.demo_header)
    return ReplayCheckOut(
        recordings_dir=result.recordings_dir,
        recording_files=result.recording_files,
        demo_start=result.demo_start,
        candidates=[CandidateReplayOut(**vars(c)) for c in result.candidates],
    )


def _result(result: air_gap_agent.CandidateResult) -> RunResultOut:
    return RunResultOut(
        row_key=result.row_key,
        outcome=result.outcome,
        proposal_id=result.proposal_id,
        status=result.status,
        trace_id=result.trace_id,
        message=result.message,
        replay_miss=result.replay_miss,
    )


@router.get("/proposals")
def list_proposals(
    deps: DepsDep,
    principal: PrincipalDep,
    status: str | None = None,
    agent: str | None = None,
    row_key: str | None = None,
) -> dict[str, Any]:
    statuses = [s for s in (status or "").split(",") if s] or None
    return proposals.listing(deps.engine, statuses=statuses, agent=agent, row_key=row_key)


@router.get("/proposals/{proposal_id}")
def get_proposal(proposal_id: int, deps: DepsDep, principal: PrincipalDep) -> dict[str, Any]:
    return proposals.detail(deps.engine, proposal_id)


@router.post("/proposals/{proposal_id}/approve")
def approve(proposal_id: int, request: Request, deps: DepsDep, principal: PrincipalDep) -> dict[str, Any]:
    _require_decider(request, deps, proposal_id, principal)
    return proposals.approve(deps, proposal_id, principal)


@router.post("/proposals/{proposal_id}/reject")
def reject(
    proposal_id: int, body: RejectBody, request: Request, deps: DepsDep, principal: PrincipalDep
) -> dict[str, Any]:
    _require_decider(request, deps, proposal_id, principal)
    return proposals.reject(deps, proposal_id, principal, body.reason)


def _require_decider(request: Request, deps: Deps, proposal_id: int, principal: Principal) -> None:
    with deps.engine.connect() as connection:
        required = proposals.get_row(connection, proposal_id)["required_role"]
    if principal.role not in (required, "admin"):
        forbid(request, principal, (required, "admin"))


@router.get("/traces/{trace_id}")
def get_trace(trace_id: str, deps: DepsDep, principal: PrincipalDep) -> dict[str, Any]:
    from agents.harness.trace import read_trace

    steps = read_trace(deps.engine, trace_id)
    if not steps:
        raise HTTPException(status_code=404, detail=f"no trace {trace_id}")
    tokens_in = sum(s["tokens_in"] or 0 for s in steps)
    tokens_out = sum(s["tokens_out"] or 0 for s in steps)
    cost = (
        tokens_in / 1000 * deps.settings.price_in_per_1k + tokens_out / 1000 * deps.settings.price_out_per_1k
    )
    with deps.engine.connect() as connection:
        owner = connection.execute(
            select(proposal.c.id, proposal.c.row_key).where(proposal.c.trace_id == trace_id)
        ).first()
    responses = [s["payload_json"] or {} for s in steps if s["step_type"] == "model_response"]
    return {
        "trace_id": trace_id,
        "proposal_id": owner[0] if owner else None,
        "row_key": owner[1] if owner else None,
        "provider": next((r.get("provider") for r in responses if r.get("provider")), None),
        "model_id": next((r.get("model_id") for r in responses if r.get("model_id")), None),
        "replayed": any(r.get("replayed") for r in responses),
        "steps": [
            {
                "seq": s["seq"],
                "step_type": s["step_type"],
                "payload": s["payload_json"],
                "tokens_in": s["tokens_in"],
                "tokens_out": s["tokens_out"],
                "latency_ms": s["latency_ms"],
                "at": s["at"],
            }
            for s in steps
        ],
        "totals": {
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "latency_ms": sum(s["latency_ms"] or 0 for s in steps),
            "cost_usd": round(cost, 4),
            "model_calls": len(responses),
        },
    }


class AutorunOut(BaseModel):
    enabled: bool
    paused: bool
    cursor: str | None


@autorun_router.post("/pause")
def pause_autorun(request: Request) -> AutorunOut:
    """The demo reset calls this before it wipes state (F12-FR-14); guarded with the scenario token."""
    return AutorunOut(**vars(request.app.state.autorun.pause()))


@autorun_router.post("/resume")
def resume_autorun(request: Request) -> AutorunOut:
    return AutorunOut(**vars(request.app.state.autorun.resume()))


@autorun_router.get("")
def autorun_state(request: Request) -> AutorunOut:
    return AutorunOut(**vars(request.app.state.autorun.state()))


__all__ = ["ProposalError", "autorun_router", "router"]
