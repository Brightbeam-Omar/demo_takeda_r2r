"""The agents service's view of the ``app`` database: the four tables it may write, as SQLAlchemy Core tables.

It connects as the restricted role ``agents_rw`` (migration 0014), which has grants on exactly these four
tables and nothing else, so a bug here cannot touch overrides, the mirror or users (F12-FR-01, F12-AC-07).
"""

import os
from collections.abc import Mapping
from datetime import datetime
from typing import Any
from urllib.parse import quote

from r2r_core import clock
from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Engine,
    Integer,
    MetaData,
    Table,
    Text,
    create_engine,
    insert,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Connection

ROLE = "agents_rw"
DEFAULT_PASSWORD = "agents_dev_only"
metadata = MetaData()
STAMP = DateTime(timezone=True)

proposal = Table(
    "proposal",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("agent_key", Text, nullable=False),
    Column("row_key", Text),
    Column("kind", Text, nullable=False),
    Column("payload_json", JSONB),
    Column("evidence_json", JSONB),
    Column("validator_result_json", JSONB),
    Column("status", Text, nullable=False),
    Column("required_role", Text, nullable=False),
    Column("created_at", STAMP, nullable=False),
    Column("decided_by", Text),
    Column("decided_at", STAMP),
    Column("decision_reason", Text),
    Column("trace_id", Text),
)
action_log = Table(
    "action_log",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("proposal_id", BigInteger, nullable=False),
    Column("action_type", Text, nullable=False),
    Column("rendered_json", JSONB),
    Column("executed_at", STAMP, nullable=False),
)
agent_trace = Table(
    "agent_trace",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("trace_id", Text, nullable=False),
    Column("seq", Integer, nullable=False),
    Column("step_type", Text, nullable=False),
    Column("payload_json", JSONB),
    Column("tokens_in", Integer),
    Column("tokens_out", Integer),
    Column("latency_ms", Integer),
    Column("at", STAMP, nullable=False),
)
audit_event = Table(
    "audit_event",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("at", STAMP, nullable=False),
    Column("actor_user_key", Text),
    Column("action", Text, nullable=False),
    Column("row_key", Text),
    Column("details_json", JSONB),
    implicit_returning=False,  # the role may INSERT but not SELECT audit_event, so no RETURNING id
)


def agents_dsn(env: Mapping[str, str] | None = None) -> str:
    """DSN for the ``app`` database as ``agents_rw`` (``AGENTS_DSN`` overrides it, for tests)."""
    source = os.environ if env is None else env
    if source.get("AGENTS_DSN"):
        return source["AGENTS_DSN"]
    password = quote(source.get("AGENTS_DB_PASSWORD") or DEFAULT_PASSWORD, safe="")
    host = source.get("POSTGRES_HOST", "postgres")
    port = source.get("POSTGRES_PORT", "5432")
    return f"postgresql+psycopg://{ROLE}:{password}@{host}:{port}/app"


def make_engine(dsn: str | None = None) -> Engine:
    return create_engine(dsn or agents_dsn(), pool_pre_ping=True)


def write_audit(
    connection: Connection,
    actor: str | None,
    action: str,
    row_key: str | None = None,
    details: Mapping[str, Any] | None = None,
    at: datetime | None = None,
) -> None:
    """Insert one ``audit_event`` row (the demo clock stamps it)."""
    connection.execute(
        insert(audit_event).values(
            at=at or clock.now(),
            actor_user_key=actor,
            action=action,
            row_key=row_key,
            details_json=dict(details) if details is not None else None,
        )
    )
