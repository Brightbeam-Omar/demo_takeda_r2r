"""publish the stage-rule inputs cycle_start_date and ud_effective (F09, OQ-060)

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-05 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("mirror_batch_pipeline", sa.Column("cycle_start_date", sa.Date(), nullable=True))
    op.add_column("mirror_batch_pipeline", sa.Column("ud_effective", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("mirror_batch_pipeline", "ud_effective")
    op.drop_column("mirror_batch_pipeline", "cycle_start_date")
