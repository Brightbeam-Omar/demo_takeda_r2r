"""F12 T8: the executor renders a ticket record and an email, and sends nothing [F12-FR-09]."""

from datetime import UTC, datetime
from pathlib import Path

import agents
import pytest
from agent_support import OPEN_DEVIATION, evidence, ticket
from agents.harness.executor import DELIVERY, EMAIL_TO, execute, render_actions, ticket_number
from sqlalchemy import Engine, text

NOW = datetime(2026, 10, 12, 7, 0, tzinfo=UTC)


def test_f12_fr09_a_ticket_record_and_an_email_are_rendered() -> None:
    (ticket_type, record), (email_type, email) = render_actions(7, ticket(), "alex", NOW)
    assert (ticket_type, email_type) == ("ticket_created", "email_queued")
    assert record["ticket_no"] == ticket_number(7) == "TKT-0007"
    assert (
        record["batch_no"] == "B5003"
        and record["priority"] == "high"
        and record["assigned_role"] == "qa_release"
    )
    assert record["created_by"] == "alex" and "S-0000404" in record["text"]
    assert len(record["evidence"]) == len(evidence())
    assert email["to"] == EMAIL_TO == "QA Release Team <qa-release@demo-pharma.example>"
    assert (
        email["subject"]
        == "[HIGH] Air gap B5003: Batch B5003: LIMS approved, no ERP usage decision (TKT-0007)"
    )
    assert (
        "Post the usage decision in the ERP" in email["body"]
        and "approved by alex on 2026-10-12" in email["body"]
    )
    assert "/agents/proposals/7" in email["body"]
    assert email["delivery"] == DELIVERY == "Sent to outbox (demo)"


def test_f12_fr09_the_email_names_the_action_for_a_deviation() -> None:
    deviation = ticket(
        recommended_action="investigate_deviation_first", open_deviations=[OPEN_DEVIATION["deviation_no"]]
    )
    _, (_, email) = render_actions(1, deviation, "admin", NOW)
    assert "Investigate the open deviation first" in email["body"]


def test_f12_fr09_nothing_in_the_service_can_send_mail() -> None:
    """Tier 1 has no outbound mail: no mail library or socket is imported anywhere in the service."""
    source = "\n".join(p.read_text() for p in Path(agents.__file__).parent.rglob("*.py"))
    for forbidden in ("smtplib", "sendmail", "import socket", "aiosmtplib", "boto3"):
        assert forbidden not in source, forbidden


@pytest.mark.integration
def test_f12_fr09_execute_writes_two_action_log_rows(agents_engine: Engine) -> None:
    with agents_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO proposal (id, agent_key, row_key, kind, status, required_role, created_at) "
                "VALUES (5, 'air_gap', 'r', 'airgap_ticket', 'approved', 'qa_release', now())"
            )
        )
        execute(connection, 5, ticket(), "alex", NOW)
    with agents_engine.connect() as connection:
        rows = connection.execute(
            text("SELECT action_type, rendered_json->>'ticket_no', rendered_json->>'delivery' "
                 "FROM action_log WHERE proposal_id = 5 ORDER BY id")
        ).all()  # fmt: skip
    assert [tuple(r) for r in rows] == [
        ("ticket_created", "TKT-0005", None),
        ("email_queued", None, DELIVERY),
    ]
