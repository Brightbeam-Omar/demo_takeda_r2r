"""bookmark and filter_preset tables (F16-FR-04, FR-05)

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-05 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "bookmark",
        sa.Column("user_key", sa.Text(), nullable=False),
        sa.Column("row_key", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_key"], ["app_user.user_key"]),
        sa.PrimaryKeyConstraint("user_key", "row_key"),
    )
    op.create_table(
        "filter_preset",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_key", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("char_length(name) BETWEEN 1 AND 60", name="ck_filter_preset_name_length"),
        sa.CheckConstraint("char_length(query) <= 2000", name="ck_filter_preset_query_length"),
        sa.ForeignKeyConstraint(["user_key"], ["app_user.user_key"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_key", "name", name="uq_filter_preset_user_name"),
    )


def downgrade() -> None:
    op.drop_table("filter_preset")
    op.drop_table("bookmark")
