"""mcha.zexprq and mcha.zexpdd: source expedite facts (F20-FR-02)

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-06 16:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("mcha", sa.Column("zexprq", sa.Date(), nullable=True))
    op.add_column("mcha", sa.Column("zexpdd", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("mcha", "zexpdd")
    op.drop_column("mcha", "zexprq")
