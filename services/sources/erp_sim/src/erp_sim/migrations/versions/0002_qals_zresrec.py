"""qals.zresrec: LIMS results recorded in the ERP via the interface

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-04 13:00:00.000000

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
    op.add_column("qals", sa.Column("zresrec", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("qals", "zresrec")
