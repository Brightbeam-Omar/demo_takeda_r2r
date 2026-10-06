"""retired need-by reason codes become the labelled F19 codes (F19-FR-06, OQ-112)

Appends a new current version for every current ``adjusted_need_by_date`` override whose reason code was
retired: ``CAMPAIGN_PUSHED_OUT`` becomes ``CAMPAIGN_PUSHED_BACK``, ``LAB_CAPACITY`` becomes
``TESTING_CAPACITY``, any other retired code becomes ``OTHER`` with the original code kept in the note. The
previous version is only flagged ``is_current = false``, as every new override version does; nothing is
edited or deleted. Each change has an ``audit_event`` by ``system``.

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-06 21:00:00.000000

"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | Sequence[str] | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_CODES = {
    "CAMPAIGN_PULLED_FORWARD", "CAMPAIGN_PUSHED_BACK", "VERBAL_CONFIRMATION", "SHELF_LIFE_CONSTRAINT",
    "SUPPLIER_DELAY", "RETEST_REQUIRED", "EXPEDITE_PRODUCTION", "EXPEDITE_SHIPPING", "TESTING_CAPACITY", "OTHER",
}  # fmt: skip
RENAMED = {"CAMPAIGN_PUSHED_OUT": "CAMPAIGN_PUSHED_BACK", "LAB_CAPACITY": "TESTING_CAPACITY"}


def upgrade() -> None:
    connection = op.get_bind()
    now = "COALESCE((SELECT now_utc FROM demo_clock WHERE id = 1), now())"
    current = connection.execute(
        sa.text(
            "SELECT id, row_key, value_json, reason_code, note, version, author_user_key FROM override_value "
            "WHERE is_current AND field = 'adjusted_need_by_date' AND reason_code IS NOT NULL ORDER BY id"
        )
    ).all()
    for row in current:
        if row.reason_code in NEW_CODES:
            continue
        code = RENAMED.get(row.reason_code, "OTHER")
        note = row.note
        if code == "OTHER":
            note = f"{row.reason_code}: {row.note}" if row.note else row.reason_code
        connection.execute(
            sa.text("UPDATE override_value SET is_current = false WHERE id = :id"), {"id": row.id}
        )
        connection.execute(
            sa.text(
                "INSERT INTO override_value (row_key, field, value_json, reason_code, note, version, "
                f"author_user_key, created_at, is_current) VALUES (:k, 'adjusted_need_by_date', "
                f"CAST(:v AS jsonb), :c, :n, :ver, :a, {now}, true)"
            ),
            {
                "k": row.row_key,
                "v": json.dumps(row.value_json),
                "c": code,
                "n": note,
                "ver": row.version + 1,
                "a": row.author_user_key,
            },
        )
        connection.execute(
            sa.text(
                "INSERT INTO audit_event (at, actor_user_key, action, row_key, details_json) VALUES "
                f"({now}, 'system', 'reason_code_migrated', :k, CAST(:d AS jsonb))"
            ),
            {
                "k": row.row_key,
                "d": json.dumps(
                    {"field": "adjusted_need_by_date", "old": row.reason_code, "new": code, "note": note}
                ),
            },
        )


def downgrade() -> None:
    """The copy is not undone: the old versions stay in the history."""
