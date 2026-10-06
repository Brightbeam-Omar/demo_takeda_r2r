"""status_log: one append-only log for status and comments (F19-FR-05, OQ-111)

Copies every ``manual_status`` override version and every ``comment`` row into the log, in time order, with
the original author and time. Nothing is updated or deleted: the old rows stay for history. One
``audit_event`` by ``system`` records the copy.

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-06 20:00:00.000000

"""

import json
from collections.abc import Sequence
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | Sequence[str] | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RAG_TO_STATUS = {"green": "on_track", "amber": "at_risk", "red": "blocked"}


def upgrade() -> None:
    op.create_table(
        "status_log",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("row_key", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=True),
        sa.Column("team", sa.Text(), nullable=True),
        sa.Column("reason_code", sa.Text(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("author_user_key", sa.Text(), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["author_user_key"], ["app_user.user_key"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_status_log_row_key", "status_log", ["row_key", "id"])
    _copy_old_rows()


def _copy_old_rows() -> None:
    connection = op.get_bind()
    entries: list[tuple[datetime, int, int, dict[str, Any]]] = []
    statuses = connection.execute(
        sa.text(
            "SELECT id, row_key, value_json, note, author_user_key, created_at FROM override_value "
            "WHERE field = 'manual_status'"
        )
    )
    for row in statuses:
        value = row.value_json
        if isinstance(value, str):
            value = json.loads(value)
        if value:
            status = RAG_TO_STATUS.get(value.get("rag"))
            entry = {"status": status, "team": value.get("team"), "comment": row.note or "Status set"}
        else:
            entry = {"status": None, "team": None, "comment": "Status cleared"}
        entries.append(
            (row.created_at, 0, row.id, {**entry, "row_key": row.row_key, "author": row.author_user_key})
        )
    comments = connection.execute(
        sa.text("SELECT id, row_key, body, author_user_key, created_at FROM comment")
    )
    for row in comments:
        entry = {"status": None, "team": None, "comment": row.body}
        entries.append(
            (row.created_at, 1, row.id, {**entry, "row_key": row.row_key, "author": row.author_user_key})
        )
    if not entries:
        return
    entries.sort(key=lambda e: (e[0], e[1], e[2]))
    insert = sa.text(
        "INSERT INTO status_log (row_key, status, team, reason_code, comment, author_user_key, at) "
        "VALUES (:row_key, :status, :team, NULL, :comment, :author, :at)"
    )
    for created_at, _, _, entry in entries:
        connection.execute(insert, {**entry, "at": created_at})
    counts = {
        "statuses": sum(1 for e in entries if e[1] == 0),
        "comments": sum(1 for e in entries if e[1] == 1),
    }
    connection.execute(
        sa.text(
            "INSERT INTO audit_event (at, actor_user_key, action, row_key, details_json) VALUES "
            "(COALESCE((SELECT now_utc FROM demo_clock WHERE id = 1), now()), 'system', "
            "'status_log_migrated', NULL, CAST(:details AS jsonb))"
        ),
        {"details": json.dumps(counts)},
    )


def downgrade() -> None:
    op.drop_index("ix_status_log_row_key", table_name="status_log")
    op.drop_table("status_log")
