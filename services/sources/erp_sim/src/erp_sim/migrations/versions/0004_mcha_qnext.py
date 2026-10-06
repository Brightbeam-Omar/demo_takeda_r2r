"""mcha.qnext: next inspection (retest) date

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-06 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("mcha", sa.Column("qnext", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("mcha", "qnext")
