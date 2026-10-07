"""The executor (F12-FR-09): what happens when a person approves a proposal.

It renders two things from templates and writes them to ``action_log``: the **ticket record** and an **email**
to the QA release team. Nothing is sent anywhere: the email is only rendered, and the UI says "Sent to outbox
(demo)". Tier 1 has no outbound mail, ever (a test guards the source for mail libraries).
"""

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from sqlalchemy import insert
from sqlalchemy.engine import Connection

from agents.air_gap.schema import AirGapTicket
from agents.db import action_log

TEMPLATES = Path(__file__).resolve().parents[1] / "templates"
EMAIL_TO = "QA Release Team <qa-release@demo-pharma.example>"
DELIVERY = "Sent to outbox (demo)"

ACTION_TEXT = {
    "post_usage_decision": "Post the usage decision in the ERP",
    "investigate_deviation_first": "Investigate the open deviation first, then post the usage decision",
    "check_interface": "Check the LIMS to ERP interface",
}


def ticket_number(proposal_id: int) -> str:
    return f"TKT-{proposal_id:04d}"


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(TEMPLATES), undefined=StrictUndefined, keep_trailing_newline=False
    )


def batch_of(ticket: AirGapTicket) -> str:
    """The batch number is the middle part of the row key (``material|batch|lot``)."""
    parts = ticket.row_key.split("|")
    return parts[1] if len(parts) == 3 else ticket.row_key


def render_actions(
    proposal_id: int, ticket: AirGapTicket, approved_by: str, approved_on: datetime
) -> list[tuple[str, dict[str, Any]]]:
    """The ``action_log`` rows for one approval: ``ticket_created`` and ``email_queued``."""
    env = _env()
    number = ticket_number(proposal_id)
    variables: dict[str, Any] = {
        "ticket": ticket,
        "ticket_no": number,
        "batch_no": batch_of(ticket),
        "action_text": ACTION_TEXT[ticket.recommended_action],
        "approved_by": approved_by,
        "approved_on": approved_on.date().isoformat(),
        "link": f"/agents/proposals/{proposal_id}",
    }
    record = {
        "ticket_no": number,
        "title": ticket.title,
        "priority": ticket.priority,
        "row_key": ticket.row_key,
        "batch_no": variables["batch_no"],
        "recommended_action": ticket.recommended_action,
        "assigned_role": ticket.recipient_role,
        "hours_in_gap": ticket.hours_in_gap,
        "evidence": [item.model_dump() for item in ticket.evidence],
        "text": env.get_template("ticket.md.j2").render(**variables).strip(),
        "created_by": approved_by,
    }
    email = {
        "to": EMAIL_TO,
        "subject": env.get_template("email_subject.txt.j2").render(**variables).strip(),
        "body": env.get_template("email_body.txt.j2").render(**variables).strip(),
        "delivery": DELIVERY,
    }
    return [("ticket_created", record), ("email_queued", email)]


def execute(
    connection: Connection,
    proposal_id: int,
    ticket: AirGapTicket,
    approved_by: str,
    now: datetime,
) -> Sequence[tuple[str, dict[str, Any]]]:
    """Render and write the two action rows (inside the caller's transaction)."""
    actions = render_actions(proposal_id, ticket, approved_by, now)
    for action_type, rendered in actions:
        connection.execute(
            insert(action_log).values(
                proposal_id=proposal_id, action_type=action_type, rendered_json=rendered, executed_at=now
            )
        )
    return actions
