"""mirror_inbound_checks, mirror_change_controls, mirror_samples and the extended mirror_deviations (F19-FR-08)

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-06 22:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | Sequence[str] | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STAMP = sa.DateTime(timezone=True)


def _mirror_columns() -> list[sa.Column]:  # type: ignore[type-arg]
    return [
        sa.Column("contract_run_id", sa.Text(), nullable=False),
        sa.Column("mirrored_at", STAMP, nullable=False),
    ]


def upgrade() -> None:
    for column in ("causal_factor", "investigation_summary", "description", "run_id"):
        op.add_column("mirror_deviations", sa.Column(column, sa.Text(), nullable=True))
    op.create_table(
        "mirror_inbound_checks",
        sa.Column("row_key", sa.Text(), nullable=False),
        sa.Column("prueflos", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=True),
        sa.Column("deadline", sa.Date(), nullable=True),
        sa.Column("failed_count", sa.BigInteger(), nullable=True),
        sa.Column("items_json", sa.Text(), nullable=True),
        sa.Column("run_id", sa.Text(), nullable=True),
        *_mirror_columns(),
        sa.PrimaryKeyConstraint("row_key"),
    )
    op.create_table(
        "mirror_change_controls",
        sa.Column("cc_no", sa.Text(), nullable=False),
        sa.Column("material_no", sa.Text(), nullable=False),
        sa.Column("batch_no", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=True),
        sa.Column("current_state", sa.Text(), nullable=True),
        sa.Column("proposed_state", sa.Text(), nullable=True),
        sa.Column("opened_on", sa.Date(), nullable=True),
        sa.Column("effective_on", sa.Date(), nullable=True),
        sa.Column("run_id", sa.Text(), nullable=True),
        *_mirror_columns(),
        sa.PrimaryKeyConstraint("cc_no", "material_no", "batch_no"),
    )
    op.create_index(
        "ix_mirror_change_controls_material_no_batch_no",
        "mirror_change_controls",
        ["material_no", "batch_no"],
    )
    op.create_table(
        "mirror_samples",
        sa.Column("row_key", sa.Text(), nullable=False),
        sa.Column("sample_id", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=True),
        sa.Column("collected_date", sa.Date(), nullable=True),
        sa.Column("approved_at", STAMP, nullable=True),
        sa.Column("run_id", sa.Text(), nullable=True),
        *_mirror_columns(),
        sa.PrimaryKeyConstraint("row_key", "sample_id"),
    )


def downgrade() -> None:
    op.drop_table("mirror_samples")
    op.drop_index("ix_mirror_change_controls_material_no_batch_no", table_name="mirror_change_controls")
    op.drop_table("mirror_change_controls")
    op.drop_table("mirror_inbound_checks")
    for column in ("run_id", "description", "investigation_summary", "causal_factor"):
        op.drop_column("mirror_deviations", column)
