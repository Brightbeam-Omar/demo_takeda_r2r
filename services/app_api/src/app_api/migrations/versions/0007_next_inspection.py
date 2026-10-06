"""mirror_batch_pipeline.next_inspection_date (F18-FR-03g)

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-06 14:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("mirror_batch_pipeline", sa.Column("next_inspection_date", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("mirror_batch_pipeline", "next_inspection_date")
