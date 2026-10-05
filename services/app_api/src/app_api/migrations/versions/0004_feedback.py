"""feedback table for the floating Feedback button (F15-FR-06, OQ-083)

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-05 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "feedback",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_key", sa.Text(), nullable=False),
        sa.Column("page", sa.Text(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.CheckConstraint("char_length(message) BETWEEN 1 AND 2000", name="ck_feedback_message_length"),
        sa.CheckConstraint("char_length(page) <= 200", name="ck_feedback_page_length"),
        sa.ForeignKeyConstraint(["user_key"], ["app_user.user_key"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_feedback_at"), "feedback", ["at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_feedback_at"), table_name="feedback")
    op.drop_table("feedback")
