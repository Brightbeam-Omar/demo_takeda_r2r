"""F12: the agents database role, open-proposal rule, reject reason and the trace id sequence

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-07 09:00:00.000000

"""

import os
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | Sequence[str] | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ROLE = "agents_rw"
DEFAULT_PASSWORD = "agents_dev_only"  # same idea as POSTGRES_PASSWORD's dev default; .env overrides it
OPEN_STATUSES = "status IN ('pending_approval','approved','executed')"

# The only tables the agents service may touch (F12-FR-01), and what it may do to each.
GRANTS = {
    "proposal": "SELECT, INSERT, UPDATE",
    "agent_trace": "SELECT, INSERT",
    "action_log": "SELECT, INSERT",
    "audit_event": "INSERT",
}
SEQUENCES = ("proposal_id_seq", "agent_trace_id_seq", "action_log_id_seq", "audit_event_id_seq")


def upgrade() -> None:
    op.add_column("proposal", sa.Column("decision_reason", sa.Text(), nullable=True))
    op.create_index(
        "uq_proposal_open",
        "proposal",
        ["row_key", "kind"],
        unique=True,
        postgresql_where=sa.text(OPEN_STATUSES),
    )
    op.execute("CREATE SEQUENCE agent_trace_seq START 1")

    password = os.environ.get("AGENTS_DB_PASSWORD") or DEFAULT_PASSWORD
    op.execute(
        sa.text(
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{ROLE}') THEN
                    CREATE ROLE {ROLE} LOGIN;
                END IF;
            END
            $$
            """
        )
    )
    # A role is cluster-wide: every migrated database re-asserts its password.
    quoted = password.replace("'", "''")
    op.execute(sa.text(f"ALTER ROLE {ROLE} WITH LOGIN PASSWORD '{quoted}'"))
    for table, privileges in GRANTS.items():
        op.execute(f"REVOKE ALL ON {table} FROM {ROLE}")
        op.execute(f"GRANT {privileges} ON {table} TO {ROLE}")
    for sequence in SEQUENCES:
        op.execute(f"GRANT USAGE ON SEQUENCE {sequence} TO {ROLE}")
    op.execute(f"GRANT USAGE ON SEQUENCE agent_trace_seq TO {ROLE}")


def downgrade() -> None:
    for table in GRANTS:
        op.execute(f"REVOKE ALL ON {table} FROM {ROLE}")
    for sequence in (*SEQUENCES, "agent_trace_seq"):
        op.execute(f"REVOKE ALL ON SEQUENCE {sequence} FROM {ROLE}")
    op.execute("DROP SEQUENCE agent_trace_seq")
    op.drop_index("uq_proposal_open", table_name="proposal", postgresql_where=sa.text(OPEN_STATUSES))
    op.drop_column("proposal", "decision_reason")
