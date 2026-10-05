"""ekpo: open purchase-order lines, and the PO reference on mseg (F17)

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-06 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ekpo",
        sa.Column("ebeln", sa.Text(), nullable=False),
        sa.Column("ebelp", sa.Text(), nullable=False),
        sa.Column("matnr", sa.Text(), nullable=False),
        sa.Column("lifnr", sa.Text(), nullable=False),
        sa.Column("eindt", sa.Date(), nullable=False),
        sa.Column("menge", sa.Numeric(13, 3), nullable=False),
        sa.Column("lgort", sa.Text(), nullable=False),
        sa.Column("is_open", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["matnr"], ["mara.matnr"]),
        sa.ForeignKeyConstraint(["lifnr"], ["lfa1.lifnr"]),
        sa.ForeignKeyConstraint(["lgort"], ["t001l.lgort"]),
        sa.PrimaryKeyConstraint("ebeln", "ebelp"),
    )
    op.create_index("ix_ekpo_updated_at", "ekpo", ["updated_at"])
    op.create_index("ix_ekpo_matnr", "ekpo", ["matnr"])
    op.add_column("mseg", sa.Column("ebeln", sa.Text(), nullable=True))
    op.add_column("mseg", sa.Column("ebelp", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("mseg", "ebelp")
    op.drop_column("mseg", "ebeln")
    op.drop_table("ekpo")
