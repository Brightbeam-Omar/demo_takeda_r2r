"""F08-FR-01: the app schema has every table of 04-data-contracts section 5, and the five users are seeded."""

from collections.abc import Callable

import pytest
from app_api.db import migrate
from app_api.models import Base
from r2r_core.db import make_engine
from sqlalchemy import inspect, text

SECTION_5_TABLES = {
    "app_user", "demo_clock", "sync_event", "watermark", "override_value", "comment", "status_log", "audit_event",
    "feedback", "bookmark", "filter_preset", "proposal", "action_log", "agent_trace", "mirror_batch_pipeline", "mirror_weekly_metrics",
    "mirror_weekly_metric_rows", "mirror_pipeline_status", "mirror_stage_reference",
    "mirror_metric_reference", "mirror_reason_codes", "mirror_deviations", "mirror_expected_deliveries",
    "mirror_inbound_checks", "mirror_change_controls", "mirror_samples",
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
        with engine.connect() as connection:
            partial = connection.execute(
                text("SELECT indexdef FROM pg_indexes WHERE indexname = 'uq_override_value_current'")
            ).scalar_one()
            jsonb = {
                (r[0], r[1])
                for r in connection.execute(
                    text(
                        "SELECT table_name, column_name FROM information_schema.columns WHERE data_type = 'jsonb'"
                    )
                )
            }
            keys = {
                r[0]: r[1]
                for r in connection.execute(
                    text(
                        "SELECT tc.table_name, string_agg(k.column_name, ',' ORDER BY k.ordinal_position) "
                        "FROM information_schema.table_constraints tc JOIN information_schema.key_column_usage k "
                        "USING (constraint_name, table_name) WHERE tc.constraint_type = 'PRIMARY KEY' GROUP BY 1"
                    )
                )
            }
        assert "UNIQUE" in partial
        assert "WHERE is_current" in partial
        assert ("mirror_batch_pipeline", "applicable_sla_json") in jsonb
        assert ("mirror_pipeline_status", "source_freshness_json") in jsonb
        assert keys["mirror_batch_pipeline"] == "row_key"
        assert keys["mirror_weekly_metric_rows"] == "metric_id,week_start,row_key"
        assert keys["mirror_deviations"] == "deviation_no,material_no,batch_no"
        assert keys["watermark"] == "object_name"
        assert "ix_mirror_batch_pipeline_stage_key" in indexes
    finally:
        engine.dispose()


@pytest.mark.integration
def test_f09_fr06_the_mirror_has_the_published_rule_inputs(make_test_database: Callable[[str], str]) -> None:
    dsn = make_test_database("app_rule_inputs")
    migrate(dsn)
    engine = make_engine(dsn)
    try:
        columns = {c["name"]: str(c["type"]) for c in inspect(engine).get_columns("mirror_batch_pipeline")}
    finally:
        engine.dispose()
    assert columns["cycle_start_date"] == "DATE" and columns["ud_effective"] == "BOOLEAN"
