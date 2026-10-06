"""deviation causal factor, investigation summary, severity vocabulary; change control (F19)

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-06 19:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("deviation", sa.Column("causal_factor", sa.Text(), nullable=True))
    op.add_column("deviation", sa.Column("investigation_summary", sa.Text(), nullable=True))
    op.drop_constraint("ck_deviation_severity", "deviation", type_="check")
    op.execute("UPDATE deviation SET severity = 'major' WHERE severity = 'critical'")
    op.create_check_constraint(
        "ck_deviation_severity", "deviation", "severity in ('minor', 'moderate', 'major')"
    )
    op.create_table(
        "change_control",
        sa.Column("cc_no", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("current_state", sa.Text(), nullable=False),
        sa.Column("proposed_state", sa.Text(), nullable=False),
        sa.Column("opened_on", sa.Date(), nullable=False),
        sa.Column("effective_on", sa.Date(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status in ('open', 'approved', 'closed', 'cancelled')", name="ck_change_control_status"
        ),
        sa.PrimaryKeyConstraint("cc_no"),
    )
    op.create_index("ix_change_control_updated_at", "change_control", ["updated_at"])
    op.create_table(
        "change_control_link",
        sa.Column("cc_no", sa.Text(), nullable=False),
        sa.Column("material_no", sa.Text(), nullable=False),
        sa.Column("batch_no", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["cc_no"], ["change_control.cc_no"]),
        sa.PrimaryKeyConstraint("cc_no", "material_no", "batch_no"),
    )
    op.create_index(
        "ix_change_control_link_material_batch", "change_control_link", ["material_no", "batch_no"]
    )
    op.create_index("ix_change_control_link_updated_at", "change_control_link", ["updated_at"])


def downgrade() -> None:
    op.drop_index("ix_change_control_link_updated_at", table_name="change_control_link")
    op.drop_index("ix_change_control_link_material_batch", table_name="change_control_link")
    op.drop_table("change_control_link")
    op.drop_index("ix_change_control_updated_at", table_name="change_control")
    op.drop_table("change_control")
    op.drop_constraint("ck_deviation_severity", "deviation", type_="check")
    op.execute("UPDATE deviation SET severity = 'major' WHERE severity = 'moderate'")
    op.create_check_constraint(
        "ck_deviation_severity", "deviation", "severity in ('minor', 'major', 'critical')"
    )
    op.drop_column("deviation", "investigation_summary")
    op.drop_column("deviation", "causal_factor")
