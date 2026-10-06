"""F21: queue columns, worker heartbeat and the run-history mirrors

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-07 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | Sequence[str] | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STAMP = sa.DateTime(timezone=True)


def _mirror_columns() -> list[sa.Column]:  # type: ignore[type-arg]
    return [
        sa.Column("contract_run_id", sa.Text(), nullable=False),
        sa.Column("mirrored_at", STAMP, nullable=False),
    ]


def upgrade() -> None:
    op.add_column("sync_event", sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("sync_event", sa.Column("objects_synced", sa.Integer(), nullable=True))
    op.add_column("sync_event", sa.Column("drain_pass_id", sa.Text(), nullable=True))
    op.create_table(
        "worker_heartbeat",
        sa.Column("worker_id", sa.Text(), nullable=False),
        sa.Column("last_loop_at", STAMP, nullable=False),
        sa.Column("last_pass_id", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("worker_id"),
    )
    op.create_table(
        "mirror_pipeline_runs",
        sa.Column("pipeline_run_id", sa.Text(), nullable=False),
        sa.Column("run_seq", sa.BigInteger(), nullable=True),
        sa.Column("started_at", STAMP, nullable=True),
        sa.Column("duration_ms", sa.BigInteger(), nullable=True),
        sa.Column("files", sa.BigInteger(), nullable=True),
        sa.Column("inserted", sa.BigInteger(), nullable=True),
        sa.Column("total", sa.BigInteger(), nullable=True),
        sa.Column("skipped", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.Text(), nullable=True),
        sa.Column("failed_step", sa.Text(), nullable=True),
        sa.Column("run_id", sa.Text(), nullable=True),
        *_mirror_columns(),
        sa.PrimaryKeyConstraint("pipeline_run_id"),
    )
    op.create_table(
        "mirror_pipeline_run_steps",
        sa.Column("pipeline_run_id", sa.Text(), nullable=False),
        sa.Column("step", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=True),
        sa.Column("started_at", STAMP, nullable=True),
        sa.Column("finished_at", STAMP, nullable=True),
        sa.Column("rows", sa.BigInteger(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("run_id", sa.Text(), nullable=True),
        *_mirror_columns(),
        sa.PrimaryKeyConstraint("pipeline_run_id", "step"),
    )


def downgrade() -> None:
    op.drop_table("mirror_pipeline_run_steps")
    op.drop_table("mirror_pipeline_runs")
    op.drop_table("worker_heartbeat")
    op.drop_column("sync_event", "drain_pass_id")
    op.drop_column("sync_event", "objects_synced")
    op.drop_column("sync_event", "attempts")
