"""Report objects: mirror_monthly_metrics, mirror_pipeline_daily, mirror_releases_weekly and three batch columns

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-06 23:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | Sequence[str] | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STAMP = sa.DateTime(timezone=True)


def _mirror_columns() -> list[sa.Column]:  # type: ignore[type-arg]
    return [
        sa.Column("contract_run_id", sa.Text(), nullable=False),
        sa.Column("mirrored_at", STAMP, nullable=False),
    ]


def upgrade() -> None:
    for column in ("need_by_at_release", "expedite_requested_on", "expedite_due_date"):
        op.add_column("mirror_batch_pipeline", sa.Column(column, sa.Date(), nullable=True))
    op.create_table(
        "mirror_monthly_metrics",
        sa.Column("metric_id", sa.Text(), nullable=False),
        sa.Column("month_start", sa.Date(), nullable=False),
        sa.Column("completed", sa.BigInteger(), nullable=True),
        sa.Column("on_time", sa.BigInteger(), nullable=True),
        sa.Column("pct", sa.Numeric(5, 1), nullable=True),
        sa.Column("run_id", sa.Text(), nullable=True),
        *_mirror_columns(),
        sa.PrimaryKeyConstraint("metric_id", "month_start"),
    )
    op.create_table(
        "mirror_pipeline_daily",
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("stage_key", sa.Text(), nullable=False),
        sa.Column("open_count", sa.BigInteger(), nullable=True),
        sa.Column("run_id", sa.Text(), nullable=True),
        *_mirror_columns(),
        sa.PrimaryKeyConstraint("day", "stage_key"),
    )
    op.create_table(
        "mirror_releases_weekly",
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("released_count", sa.BigInteger(), nullable=True),
        sa.Column("run_id", sa.Text(), nullable=True),
        *_mirror_columns(),
        sa.PrimaryKeyConstraint("week_start"),
    )


def downgrade() -> None:
    op.drop_table("mirror_releases_weekly")
    op.drop_table("mirror_pipeline_daily")
    op.drop_table("mirror_monthly_metrics")
    for column in ("expedite_due_date", "expedite_requested_on", "need_by_at_release"):
        op.drop_column("mirror_batch_pipeline", column)
