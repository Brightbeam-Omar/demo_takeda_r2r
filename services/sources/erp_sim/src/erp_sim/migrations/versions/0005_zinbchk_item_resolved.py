"""zinbchk_item and the resolved inbound status (F19)

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-06 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_zinbchk_status", "zinbchk", type_="check")
    op.create_check_constraint(
        "ck_zinbchk_status", "zinbchk", "status in ('open', 'passed', 'resolved', 'failed')"
    )
    op.create_table(
        "zinbchk_item",
        sa.Column("prueflos", sa.Text(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("check_code", sa.Text(), nullable=False),
        sa.Column("check_label", sa.Text(), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "outcome in ('PASS', 'FAIL', 'PENDING', 'NO', 'COMP', 'APRV', 'DCPS')",
            name="ck_zinbchk_item_outcome",
        ),
        sa.ForeignKeyConstraint(["prueflos"], ["zinbchk.prueflos"]),
        sa.PrimaryKeyConstraint("prueflos", "seq"),
    )
    op.create_index("ix_zinbchk_item_updated_at", "zinbchk_item", ["updated_at"])


def downgrade() -> None:
    op.drop_index("ix_zinbchk_item_updated_at", table_name="zinbchk_item")
    op.drop_table("zinbchk_item")
    op.drop_constraint("ck_zinbchk_status", "zinbchk", type_="check")
    op.create_check_constraint("ck_zinbchk_status", "zinbchk", "status in ('open', 'passed', 'failed')")
