"""mirror_expected_deliveries and mirror_stage_reference.show_card (F17-FR-03, FR-04)

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-06 11:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mirror_expected_deliveries",
        sa.Column("ebeln", sa.Text(), nullable=False),
        sa.Column("ebelp", sa.Text(), nullable=False),
        sa.Column("material_no", sa.Text(), nullable=True),
        sa.Column("material_desc", sa.Text(), nullable=True),
        sa.Column("molecule_type", sa.Text(), nullable=True),
        sa.Column("material_class", sa.Text(), nullable=True),
        sa.Column("supplier_id", sa.Text(), nullable=True),
        sa.Column("supplier_name", sa.Text(), nullable=True),
        sa.Column("campaign", sa.Text(), nullable=True),
        sa.Column("scheduled_date", sa.Date(), nullable=True),
        sa.Column("quantity", sa.Numeric(13, 3), nullable=True),
        sa.Column("planned_location", sa.Text(), nullable=True),
        sa.Column("planned_location_type", sa.Text(), nullable=True),
        sa.Column("overdue", sa.Boolean(), nullable=True),
        sa.Column("run_id", sa.Text(), nullable=True),
        sa.Column("contract_run_id", sa.Text(), nullable=False),
        sa.Column("mirrored_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("ebeln", "ebelp"),
    )
    op.create_index(
        "ix_mirror_expected_deliveries_material_no", "mirror_expected_deliveries", ["material_no"]
    )
    op.add_column("mirror_stage_reference", sa.Column("show_card", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("mirror_stage_reference", "show_card")
    op.drop_index("ix_mirror_expected_deliveries_material_no", table_name="mirror_expected_deliveries")
    op.drop_table("mirror_expected_deliveries")
