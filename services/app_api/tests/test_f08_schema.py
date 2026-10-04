"""F08-FR-01: the app schema has every table of 04-data-contracts section 5, and the five users are seeded."""

from collections.abc import Callable

import pytest
from app_api.db import migrate
from app_api.models import Base
from r2r_core.db import make_engine
from sqlalchemy import inspect, text

SECTION_5_TABLES = {
    "app_user", "demo_clock", "sync_event", "watermark", "override_value", "comment", "audit_event",
    "proposal", "action_log", "agent_trace", "mirror_batch_pipeline", "mirror_weekly_metrics",
    "mirror_weekly_metric_rows", "mirror_pipeline_status", "mirror_stage_reference",
    "mirror_metric_reference", "mirror_reason_codes", "mirror_deviations",
}  # fmt: skip


def test_f08_fr01_models_cover_every_section_5_table() -> None:
    assert set(Base.metadata.tables) == SECTION_5_TABLES


@pytest.mark.integration
def test_f08_fr01_migration_creates_tables_and_seeds_users(make_test_database: Callable[[str], str]) -> None:
    dsn = make_test_database("app_schema")
    migrate(dsn)
    migrate(dsn)  # running again changes nothing (idempotent)
    engine = make_engine(dsn)
    try:
        assert set(inspect(engine).get_table_names()) - {"alembic_version"} == SECTION_5_TABLES
        with engine.connect() as connection:
            users = connection.execute(
                text("SELECT user_key, display_name, role FROM app_user ORDER BY 1")
            ).all()
            indexes = {row[0] for row in connection.execute(text("SELECT indexname FROM pg_indexes"))}
        assert [tuple(user) for user in users] == [
            ("admin", "Admin", "admin"),
            ("alex", "Alex", "qa_release"),
            ("pat", "Pat", "planner"),
            ("quinn", "Quinn", "qc_lead"),
            ("sam", "Sam", "viewer"),
        ]
        assert "uq_override_value_current" in indexes
        assert "ix_mirror_batch_pipeline_stage_key" in indexes
    finally:
        engine.dispose()
