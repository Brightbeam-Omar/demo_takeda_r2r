"""override_value.field accepts manual_hold and release_on_coa (F18-FR-08, OQ-103)

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-06 15:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD = "field IN ('adjusted_need_by_date','expedite','manual_status','delivery_date','delivery_location')"
NEW = (
    "field IN ('adjusted_need_by_date','expedite','manual_status','delivery_date','delivery_location',"
    "'manual_hold','release_on_coa')"
)


def upgrade() -> None:
    op.drop_constraint("ck_override_value_field", "override_value", type_="check")
    op.create_check_constraint("ck_override_value_field", "override_value", NEW)


def downgrade() -> None:
    op.drop_constraint("ck_override_value_field", "override_value", type_="check")
    op.create_check_constraint("ck_override_value_field", "override_value", OLD)
