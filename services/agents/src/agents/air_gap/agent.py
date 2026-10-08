"""The air-gap agent: candidates in, proposals out (F12-FR-08).

For each candidate the generic runner works with read-only tools, the model drafts an ``AirGapTicket``, the
validator checks it, and the result is stored as a proposal. Every step is traced. The agent never decides:
a person approves or rejects, and approval re-validates.
"""

from dataclasses import dataclass, field
from typing import Any

from r2r_core import clock
from sqlalchemy.exc import IntegrityError

from agents.air_gap.candidates import (
    AGENT_KEY,
    Candidate,
    air_gap_rows,
    row_keys_with_proposals,
)
from agents.air_gap.schema import AirGapTicket
from agents.air_gap.validator import validate_ticket
from agents.auth import Principal
from agents.db import write_audit
from agents.deps import Deps
from agents.gateway.base import GatewayError, ToolSpec
from agents.gateway.replay import ReplayMiss
from agents.harness import proposals
from agents.harness.runner import AgentSpec, RunOutcome, run_agent
from agents.harness.trace import Trace, new_trace_id
from agents.prompts import load_prompt
from agents.tools.http import ReadOnlyHttp, ToolError
from agents.tools.registry import read_only_tools

PROMPT_VERSION = "v1"
NAME = "Air-gap agent"
PURPOSE = (
    "Gathers and reconciles evidence across the LIMS, the ERP and the QMS for a batch whose approved result "
    "never reached the ERP, and drafts a ticket. A rule validator checks it and a person decides."
)


@dataclass
class CandidateResult:
    row_key: str
    outcome: str  # created | skipped | error
    proposal_id: int | None = None
    status: str | None = None
    trace_id: str | None = None
    message: str = ""
    replay_miss: dict[str, str] | None = None


@dataclass
class RunSummary:
    results: list[CandidateResult] = field(default_factory=list)

    def of(self, outcome: str) -> list[CandidateResult]:
        return [r for r in self.results if r.outcome == outcome]


def build_spec(http: ReadOnlyHttp) -> AgentSpec:
    prompt = load_prompt(AGENT_KEY, PROMPT_VERSION)
    return AgentSpec(
        key=AGENT_KEY,
        prompt_version=PROMPT_VERSION,
        system=prompt.system,
        tools=read_only_tools(http),
        output_tool=ToolSpec(
            name="submit_ticket",
            description="Submit the ticket. Call this exactly once, after you have read the evidence.",
            input_schema=AirGapTicket.model_json_schema(),
        ),
        output_model=AirGapTicket,
    )


def run(
    deps: Deps, principal: Principal | None, *, row_key: str | None = None, autorun: bool = False
) -> RunSummary:
    """Run the agent for every candidate (or one row). ``principal`` is None for autorun (service user)."""
    demo_user = principal.demo_header if principal else deps.settings.service_user
    summary = RunSummary()
    found = air_gap_rows(deps.http, demo_user)
    if row_key is not None:
        found = [c for c in found if c.row_key == row_key]
        if not found:
            summary.results.append(
                CandidateResult(row_key, "error", message="that row is not an air gap now")
            )
    blocked = row_keys_with_proposals(deps.engine, open_only=not autorun)
    for candidate in found:
        if candidate.row_key in blocked:
            reason = "has been proposed before" if autorun else "already has an open proposal"
            summary.results.append(CandidateResult(candidate.row_key, "skipped", message=reason))
            continue
        summary.results.append(run_candidate(deps, candidate, demo_user))
    with deps.engine.begin() as connection:
        write_audit(
            connection,
            principal.user_key if principal else f"agent:{AGENT_KEY}",
            "agent_run",
            row_key,
            {
                "agent": AGENT_KEY,
                "autorun": autorun,
                "created": [r.proposal_id for r in summary.of("created")],
                "skipped": [r.row_key for r in summary.of("skipped")],
                "errors": [r.row_key for r in summary.of("error")],
            },
        )
    return summary


def run_candidate(deps: Deps, candidate: Candidate, demo_user: str | None) -> CandidateResult:
    trace = Trace(deps.engine, new_trace_id(deps.engine))
    prompt = load_prompt(AGENT_KEY, PROMPT_VERSION)
    user_message = prompt.render_user(
        row_key=candidate.row_key,
        batch_no=candidate.batch_no,
        material_no=candidate.material_no,
        air_gap_hours=candidate.air_gap_hours,
        threshold_hours=deps.profile.air_gap.threshold_hours,
        high_priority_days=deps.profile.agents.air_gap.high_priority_days,
        today=clock.today().isoformat(),
    )
    try:
        outcome = run_agent(
            build_spec(deps.http),
            deps.gateway,
            trace,
            user_message=user_message,
            input_payload={
                "agent": AGENT_KEY,
                "prompt_version": PROMPT_VERSION,
                "row_key": candidate.row_key,
                "batch_no": candidate.batch_no,
                "material_no": candidate.material_no,
                "air_gap_hours": candidate.air_gap_hours,
                "provider": deps.gateway.provider,
            },
            demo_user=demo_user,
        )
    except ReplayMiss as miss:
        trace.step("decision", {"outcome": "replay_miss", "key": miss.key, "hint": miss.hint})
        return CandidateResult(
            candidate.row_key,
            "error",
            trace_id=trace.trace_id,
            message=f"No recording for {candidate.batch_no}: record it or run live",
            replay_miss={"key": miss.key, "hint": miss.hint},
        )
    except (GatewayError, ToolError) as error:
        trace.step("decision", {"outcome": "model_error", "message": str(error)})
        return CandidateResult(candidate.row_key, "error", trace_id=trace.trace_id, message=str(error))
    return _store(deps, candidate, demo_user, trace, outcome)


def _store(
    deps: Deps, candidate: Candidate, demo_user: str | None, trace: Trace, outcome: RunOutcome
) -> CandidateResult:
    payload: dict[str, Any]
    evidence: list[Any]
    if isinstance(outcome.output, AirGapTicket):
        ticket = outcome.output
        result = validate_ticket(ticket, deps.validation_context(demo_user))
        payload, evidence = ticket.model_dump(mode="json"), [e.model_dump() for e in ticket.evidence]
    else:
        result = proposals.failure_result(f"The run produced no ticket: {outcome.message}")
        payload, evidence = {"error": outcome.message, "run_status": outcome.status}, []
    trace.step("validation", {"trigger": "run", **result.model_dump(mode="json")})
    try:
        with deps.engine.begin() as connection:
            proposal_id, status = proposals.create(
                connection,
                row_key=candidate.row_key,
                payload=payload,
                evidence=evidence,
                result=result,
                trace_id=trace.trace_id,
            )
    except IntegrityError:  # a concurrent run stored an open proposal for this row first
        trace.step("decision", {"outcome": "skipped", "reason": "an open proposal already exists"})
        return CandidateResult(
            candidate.row_key, "skipped", trace_id=trace.trace_id, message="already has an open proposal"
        )
    trace.step(
        "decision",
        {"outcome": "proposed" if result.passed else "rejected_by_validator", "status": status,
         "headline": result.headline},
    )  # fmt: skip
    trace.step("action", {"type": "proposal_stored", "proposal_id": proposal_id, "status": status})
    return CandidateResult(
        candidate.row_key, "created", proposal_id, status, trace.trace_id, message=result.headline or ""
    )
