"""Proposals: store, list, approve and reject (F12-FR-08).

A proposal is the agent's draft plus the validator's verdict. ``pending_approval`` means a person may decide;
``rejected_by_validator`` is final (the only way forward is to run the agent again). **Approve re-runs V1-V6
first**: the world may have moved since the draft (a usage decision posted, an interface record arriving),
and an approval must never act on stale facts. Approve is idempotent. Every decision is audited and appended
to the run's trace.
"""

from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError
from r2r_core import clock
from sqlalchemy import Engine, func, insert, select, update
from sqlalchemy.engine import Connection

from agents.air_gap.candidates import AGENT_KEY
from agents.air_gap.schema import AirGapTicket
from agents.air_gap.validator import RuleResult, ValidatorResult, validate_payload
from agents.auth import Principal
from agents.db import action_log, proposal, write_audit
from agents.deps import Deps
from agents.harness import executor
from agents.harness.trace import Trace

STATUSES = ("pending_approval", "rejected_by_validator", "approved", "rejected", "executed")
AGENT_ACTOR = f"agent:{AGENT_KEY}"
REASON_LENGTH = (3, 200)


class ProposalError(Exception):
    status_code = 400

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class NotFoundError(ProposalError):
    status_code = 404


class ConflictError(ProposalError):
    status_code = 409


class InvalidError(ProposalError):
    status_code = 422


def batch_of_row_key(row_key: str | None) -> str | None:
    parts = (row_key or "").split("|")
    return parts[1] if len(parts) == 3 else None


def _summary(row: Mapping[str, Any]) -> dict[str, Any]:
    payload = row["payload_json"] or {}
    return {
        "id": row["id"],
        "agent_key": row["agent_key"],
        "kind": row["kind"],
        "row_key": row["row_key"],
        "batch_no": batch_of_row_key(row["row_key"]),
        "status": row["status"],
        "required_role": row["required_role"],
        "created_at": row["created_at"],
        "decided_by": row["decided_by"],
        "decided_at": row["decided_at"],
        "decision_reason": row["decision_reason"],
        "trace_id": row["trace_id"],
        "title": payload.get("title"),
        "priority": payload.get("priority"),
        "recommended_action": payload.get("recommended_action"),
        "hours_in_gap": payload.get("hours_in_gap"),
        "error": payload.get("error"),
    }


def get_row(connection: Connection, proposal_id: int, *, lock: bool = False) -> dict[str, Any]:
    query = select(proposal).where(proposal.c.id == proposal_id)
    if lock:
        query = query.with_for_update()
    row = connection.execute(query).mappings().first()
    if row is None:
        raise NotFoundError(f"no proposal {proposal_id}")
    return dict(row)


def detail(engine: Engine, proposal_id: int) -> dict[str, Any]:
    with engine.connect() as connection:
        row = get_row(connection, proposal_id)
        actions = connection.execute(
            select(action_log).where(action_log.c.proposal_id == proposal_id).order_by(action_log.c.id)
        ).mappings()
        return {
            **_summary(row),
            "payload": row["payload_json"],
            "evidence": row["evidence_json"] or [],
            "validator": row["validator_result_json"],
            "actions": [
                {"id": a["id"], "action_type": a["action_type"], "rendered": a["rendered_json"],
                 "executed_at": a["executed_at"]}
                for a in actions
            ],
        }  # fmt: skip


def listing(
    engine: Engine, *, statuses: list[str] | None, agent: str | None, row_key: str | None = None
) -> dict[str, Any]:
    """Proposals newest first, and the count per status over all proposals (the tabs)."""
    query = select(proposal).order_by(proposal.c.id.desc())
    if statuses:
        query = query.where(proposal.c.status.in_(statuses))
    if agent:
        query = query.where(proposal.c.agent_key == agent)
    if row_key:
        query = query.where(proposal.c.row_key == row_key)
    with engine.connect() as connection:
        rows = [_summary(dict(r)) for r in connection.execute(query).mappings()]
        counts = {
            status: n
            for status, n in connection.execute(
                select(proposal.c.status, func.count()).group_by(proposal.c.status)
            )
        }
    return {"counts": {status: int(counts.get(status, 0)) for status in STATUSES}, "rows": rows}


def latest_by_row(engine: Engine, row_keys: list[str]) -> dict[str, dict[str, Any]]:
    """The newest proposal of each row (what the Insights column and the drawer line show)."""
    with engine.connect() as connection:
        rows = connection.execute(
            select(proposal).where(proposal.c.row_key.in_(row_keys)).order_by(proposal.c.id)
        ).mappings()
        return {r["row_key"]: _summary(dict(r)) for r in rows}


def create(
    connection: Connection,
    *,
    row_key: str,
    payload: Mapping[str, Any],
    evidence: list[Any],
    result: ValidatorResult,
    trace_id: str,
) -> tuple[int, str]:
    status = "pending_approval" if result.passed else "rejected_by_validator"
    proposal_id = connection.execute(
        insert(proposal)
        .values(
            agent_key=AGENT_KEY,
            row_key=row_key,
            kind="airgap_ticket",
            payload_json=dict(payload),
            evidence_json=evidence,
            validator_result_json=result.model_dump(mode="json"),
            status=status,
            required_role="qa_release",
            created_at=clock.now(),
            trace_id=trace_id,
        )
        .returning(proposal.c.id)
    ).scalar_one()
    action = "proposal_created" if result.passed else "proposal_rejected_by_validator"
    write_audit(
        connection,
        AGENT_ACTOR,
        action,
        row_key,
        {"proposal_id": proposal_id, "trace_id": trace_id, "headline": result.headline},
    )
    return proposal_id, status


# --- decisions ---------------------------------------------------------------------------------------


def approve(deps: Deps, proposal_id: int, principal: Principal) -> dict[str, Any]:
    """Re-validate, then execute. Idempotent: an executed proposal is returned unchanged."""
    with deps.engine.connect() as connection:
        row = get_row(connection, proposal_id)
    if row["status"] == "executed":
        return detail(deps.engine, proposal_id)
    if row["status"] != "pending_approval":
        raise ConflictError(f"proposal {proposal_id} is {row['status']} and cannot be approved")
    result = validate_payload(row["payload_json"], deps.validation_context(principal.demo_header))
    trace = Trace.resume(deps.engine, row["trace_id"]) if row["trace_id"] else None
    if trace:
        trace.step(
            "validation", {"trigger": "approve", "by": principal.user_key, **result.model_dump(mode="json")}
        )
    now = clock.now()
    with deps.engine.begin() as connection:
        locked = get_row(connection, proposal_id, lock=True)
        if locked["status"] == "executed":
            pass  # a concurrent approval won: nothing more to do
        elif locked["status"] != "pending_approval":
            raise ConflictError(f"proposal {proposal_id} is {locked['status']} and cannot be approved")
        elif not result.passed:
            connection.execute(
                update(proposal)
                .where(proposal.c.id == proposal_id)
                .values(
                    status="rejected_by_validator",
                    validator_result_json=result.model_dump(mode="json"),
                    decision_reason=result.headline,
                )
            )
            write_audit(
                connection,
                principal.user_key,
                "proposal_rejected_by_validator",
                locked["row_key"],
                {"proposal_id": proposal_id, "source": "approve", "headline": result.headline},
            )
            if trace:
                trace.step(
                    "decision",
                    {"outcome": "rejected_by_validator", "attempted_by": principal.user_key,
                     "headline": result.headline},
                )  # fmt: skip
        else:
            ticket = AirGapTicket.model_validate(locked["payload_json"])
            connection.execute(
                update(proposal)
                .where(proposal.c.id == proposal_id)
                .values(
                    status="executed",
                    decided_by=principal.user_key,
                    decided_at=now,
                    validator_result_json=result.model_dump(mode="json"),
                )
            )
            actions = executor.execute(connection, proposal_id, ticket, principal.user_key, now)
            number = executor.ticket_number(proposal_id)
            write_audit(
                connection, principal.user_key, "proposal_approved", locked["row_key"],
                {"proposal_id": proposal_id, "trace_id": locked["trace_id"]},
            )  # fmt: skip
            write_audit(
                connection, principal.user_key, "proposal_executed", locked["row_key"],
                {"proposal_id": proposal_id, "ticket_no": number, "actions": [a for a, _ in actions]},
            )  # fmt: skip
            if trace:
                trace.step("decision", {"outcome": "approved", "by": principal.user_key})
                trace.step(
                    "action",
                    {"type": "executed", "ticket_no": number, "actions": [a for a, _ in actions],
                     "delivery": executor.DELIVERY},
                )  # fmt: skip
    return detail(deps.engine, proposal_id)


def reject(deps: Deps, proposal_id: int, principal: Principal, reason: str) -> dict[str, Any]:
    text = reason.strip()
    if not REASON_LENGTH[0] <= len(text) <= REASON_LENGTH[1]:
        raise InvalidError(f"a reason of {REASON_LENGTH[0]} to {REASON_LENGTH[1]} characters is required")
    with deps.engine.begin() as connection:
        row = get_row(connection, proposal_id, lock=True)
        if row["status"] != "pending_approval":
            raise ConflictError(f"proposal {proposal_id} is {row['status']} and cannot be rejected")
        connection.execute(
            update(proposal)
            .where(proposal.c.id == proposal_id)
            .values(
                status="rejected", decided_by=principal.user_key, decided_at=clock.now(), decision_reason=text
            )
        )
        write_audit(
            connection, principal.user_key, "proposal_rejected", row["row_key"],
            {"proposal_id": proposal_id, "reason": text},
        )  # fmt: skip
    if row["trace_id"]:
        Trace.resume(deps.engine, row["trace_id"]).step(
            "decision", {"outcome": "rejected", "by": principal.user_key, "reason": text}
        )
    return detail(deps.engine, proposal_id)


def failure_result(message: str) -> ValidatorResult:
    """The verdict for a run with no valid ticket (OQ-145): V0 failed, the other rules did not run."""
    from agents.air_gap.validator import RULES

    rules = [RuleResult(id="V0", name="The run produced a ticket", passed=False, message=message)]
    rules += [
        RuleResult(id=rule, name=name, passed=False, message="not run: the run produced no ticket")
        for rule, name in RULES.items()
    ]
    return ValidatorResult(
        passed=False, headline=message, rules=rules, evidence=[], checked_at=clock.now().isoformat()
    )


__all__ = ["ValidationError"]
