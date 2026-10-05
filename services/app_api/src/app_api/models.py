"""Tables of the ``app`` database (04-data-contracts section 5).

F04 owns ``demo_clock``. F08 adds the sync tables, the eight ``mirror_*`` tables and ``app_user``. The
tables of F09 (overrides, comments, audit) and F12 (proposals, actions, traces) are created now because the
contract lists them together, so the schema is one migration; their code arrives with those features.

Times in ``sync_event`` and ``watermark`` are infrastructure time (Postgres ``now()``), not the demo clock
(OQ-054). ``audit_event.at`` is the demo clock.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Table,
    Text,
    UniqueConstraint,
    false,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

STAMP = DateTime(timezone=True)


class Base(DeclarativeBase):
    pass


class DemoClock(Base):
    """The demo clock: one row. It moves only through the scenario service (set or advance).

    No ``updated_at``: this table *is* the clock.
    """

    __tablename__ = "demo_clock"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    now_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    frozen: Mapped[bool] = mapped_column(Boolean, server_default=false())  # reserved; always false for now
    __table_args__ = (CheckConstraint("id = 1", name="ck_demo_clock_single_row"),)


class AppUser(Base):
    __tablename__ = "app_user"
    user_key: Mapped[str] = mapped_column(Text, primary_key=True)
    display_name: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text)
    __table_args__ = (
        CheckConstraint(
            "role IN ('planner','qc_lead','qa_release','viewer','admin')", name="ck_app_user_role"
        ),
    )


class SyncEvent(Base):
    """The queue (ADR-001). ``run_id`` is informational: the worker mirrors what is currently published."""

    __tablename__ = "sync_event"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(Text)
    run_id: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="pending")
    received_at: Mapped[datetime] = mapped_column(STAMP, server_default=func.now())
    claimed_at: Mapped[datetime | None] = mapped_column(STAMP)
    finished_at: Mapped[datetime | None] = mapped_column(STAMP)
    error: Mapped[str | None] = mapped_column(Text)
    rows_upserted: Mapped[int | None] = mapped_column(Integer)
    __table_args__ = (
        CheckConstraint("source IN ('webhook','poll','manual')", name="ck_sync_event_source"),
        CheckConstraint("status IN ('pending','claimed','done','failed')", name="ck_sync_event_status"),
        Index("ix_sync_event_status_received", "status", "received_at"),
    )


class Watermark(Base):
    """One row per mirrored object: the contract run it was last synced from."""

    __tablename__ = "watermark"
    object_name: Mapped[str] = mapped_column(Text, primary_key=True)
    run_id: Mapped[str] = mapped_column(Text)
    synced_at: Mapped[datetime] = mapped_column(STAMP, server_default=func.now())


class OverrideValue(Base):
    """Insert-only versions of human input. One current row per ``(row_key, field)``."""

    __tablename__ = "override_value"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    row_key: Mapped[str] = mapped_column(Text)
    field: Mapped[str] = mapped_column(Text)
    value_json: Mapped[Any] = mapped_column(JSONB, nullable=True)
    reason_code: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer)
    author_user_key: Mapped[str] = mapped_column(ForeignKey("app_user.user_key"))
    created_at: Mapped[datetime] = mapped_column(STAMP)
    is_current: Mapped[bool] = mapped_column(Boolean, server_default=false())
    __table_args__ = (
        CheckConstraint(
            "field IN ('adjusted_need_by_date','expedite','manual_status','delivery_date',"
            "'delivery_location')",
            name="ck_override_value_field",
        ),
        Index(
            "uq_override_value_current",
            "row_key",
            "field",
            unique=True,
            postgresql_where=text("is_current"),
        ),
    )


class Comment(Base):
    __tablename__ = "comment"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    row_key: Mapped[str] = mapped_column(Text, index=True)
    body: Mapped[str] = mapped_column(Text)
    author_user_key: Mapped[str] = mapped_column(ForeignKey("app_user.user_key"))
    created_at: Mapped[datetime] = mapped_column(STAMP)


class AuditEvent(Base):
    """Every override, comment, approval, rejection, agent action and rejected webhook."""

    __tablename__ = "audit_event"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(STAMP, index=True)
    actor_user_key: Mapped[str | None] = mapped_column(Text)  # `system` for system rows
    action: Mapped[str] = mapped_column(Text)
    row_key: Mapped[str | None] = mapped_column(Text, index=True)
    details_json: Mapped[Any] = mapped_column(JSONB, nullable=True)


class Feedback(Base):
    """Free-text feedback from the floating button (F15-FR-06). Insert-only and not audited (OQ-083)."""

    __tablename__ = "feedback"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(STAMP, index=True)  # demo clock
    user_key: Mapped[str] = mapped_column(ForeignKey("app_user.user_key"))
    page: Mapped[str] = mapped_column(Text)
    message: Mapped[str] = mapped_column(Text)
    __table_args__ = (
        CheckConstraint("char_length(message) BETWEEN 1 AND 2000", name="ck_feedback_message_length"),
        CheckConstraint("char_length(page) <= 200", name="ck_feedback_page_length"),
    )


class Bookmark(Base):
    """A user's star on one row (F16-FR-04). Personal, so not audited (OQ-091)."""

    __tablename__ = "bookmark"
    user_key: Mapped[str] = mapped_column(ForeignKey("app_user.user_key"), primary_key=True)
    row_key: Mapped[str] = mapped_column(Text, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(STAMP)  # demo clock


class FilterPreset(Base):
    """A saved Overview filter query, per user (F16-FR-05). ``period`` is stored literally (OQ-089)."""

    __tablename__ = "filter_preset"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_key: Mapped[str] = mapped_column(ForeignKey("app_user.user_key"))
    name: Mapped[str] = mapped_column(Text)
    query: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(STAMP)  # demo clock
    __table_args__ = (
        UniqueConstraint("user_key", "name", name="uq_filter_preset_user_name"),
        CheckConstraint("char_length(name) BETWEEN 1 AND 60", name="ck_filter_preset_name_length"),
        CheckConstraint("char_length(query) <= 2000", name="ck_filter_preset_query_length"),
    )


class Proposal(Base):
    __tablename__ = "proposal"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    agent_key: Mapped[str] = mapped_column(Text)
    row_key: Mapped[str | None] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    payload_json: Mapped[Any] = mapped_column(JSONB, nullable=True)
    evidence_json: Mapped[Any] = mapped_column(JSONB, nullable=True)
    validator_result_json: Mapped[Any] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(Text)
    required_role: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(STAMP)
    decided_by: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime | None] = mapped_column(STAMP)
    trace_id: Mapped[str | None] = mapped_column(Text, index=True)
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending_approval','rejected_by_validator','approved','rejected','executed')",
            name="ck_proposal_status",
        ),
    )


class ActionLog(Base):
    __tablename__ = "action_log"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    proposal_id: Mapped[int] = mapped_column(ForeignKey("proposal.id"))
    action_type: Mapped[str] = mapped_column(Text)
    rendered_json: Mapped[Any] = mapped_column(JSONB, nullable=True)
    executed_at: Mapped[datetime] = mapped_column(STAMP)


class AgentTrace(Base):
    __tablename__ = "agent_trace"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    trace_id: Mapped[str] = mapped_column(Text)
    seq: Mapped[int] = mapped_column(Integer)
    step_type: Mapped[str] = mapped_column(Text)
    payload_json: Mapped[Any] = mapped_column(JSONB, nullable=True)
    tokens_in: Mapped[int | None] = mapped_column(Integer)
    tokens_out: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    at: Mapped[datetime] = mapped_column(STAMP)
    __table_args__ = (
        CheckConstraint(
            "step_type IN ('input','tool_call','tool_result','model_request','model_response',"
            "'validation','decision','action')",
            name="ck_agent_trace_step_type",
        ),
        Index("ix_agent_trace_trace_seq", "trace_id", "seq"),
    )


# --- the mirror ------------------------------------------------------------------------------------------
# One table per published object: the object's columns (native types, `jsonb` for the *_json columns), plus
# `contract_run_id` and `mirrored_at`. The column lists are the contract of 04-data-contracts section 4; the
# mirror writer reads the same lists, so a column added here is copied automatically.

TEXT, DATE, TIMESTAMP, INTEGER, BOOLEAN, JSON = Text, Date, STAMP, BigInteger, Boolean, JSONB
PCT = Numeric(5, 1)
QUANTITY = Numeric(13, 3)

MirrorColumns = tuple[tuple[str, Any], ...]

BATCH_PIPELINE_COLUMNS: MirrorColumns = (
    ("row_key", TEXT), ("material_no", TEXT), ("material_desc", TEXT), ("material_class", TEXT),
    ("molecule_type", TEXT), ("supplier_id", TEXT), ("supplier_name", TEXT), ("supplier_batch", TEXT),
    ("batch_no", TEXT), ("batch_status_code", TEXT), ("inspection_lot_no", TEXT), ("lot_type", TEXT),
    ("lot_start_date", DATE), ("storage_location", TEXT), ("location_type", TEXT),
    ("received_location_type", TEXT), ("stock_category", TEXT), ("gr_date", DATE),
    ("transfer_to_site_date", DATE), ("inbound_check_status", TEXT), ("inbound_check_completed_date", DATE),
    ("sample_id", TEXT), ("sample_collected_date", DATE), ("offsite_test", BOOLEAN), ("external_lab", TEXT),
    ("sample_shipped_date", DATE), ("lims_status", TEXT), ("lims_approved_date", DATE),
    ("lims_approved_at", TIMESTAMP), ("ud_code", TEXT), ("ud_date", DATE),
    ("erp_results_recorded_at", TIMESTAMP), ("campaign", TEXT), ("system_need_by_date", DATE),
    ("open_deviation_count", INTEGER), ("closed_deviation_count", INTEGER),
    ("stage_key", TEXT), ("stage_rule_id", TEXT), ("cycle_start_date", DATE),
    ("ud_effective", BOOLEAN), ("stage_sort", INTEGER), ("current_stage_entry_date", DATE),
    ("lims_rejected", BOOLEAN), ("receipt_entry", DATE), ("receipt_exit", DATE), ("call_off_entry", DATE),
    ("call_off_exit", DATE), ("sampling_entry", DATE), ("sampling_exit", DATE), ("qc_ship_entry", DATE),
    ("qc_ship_exit", DATE), ("qc_testing_entry", DATE), ("qc_testing_exit", DATE),
    ("qa_release_entry", DATE), ("qa_release_exit", DATE), ("applicable_sla_json", JSON),
    ("source_refs_json", JSON), ("system_need_by_locked", DATE), ("on_hold", BOOLEAN),
    ("erp_blocked", BOOLEAN), ("re_eval", BOOLEAN), ("offsite", BOOLEAN), ("full_spec", BOOLEAN),
    ("ud_rejected", BOOLEAN), ("deviation_light", TEXT), ("inbound_light", TEXT), ("snapshot_date", DATE),
    ("run_id", TEXT), ("published_at", TIMESTAMP),
)  # fmt: skip

# object name -> (mirror table name, columns, primary key, extra indexes)
MIRRORS: dict[str, tuple[str, MirrorColumns, tuple[str, ...], tuple[tuple[str, ...], ...]]] = {
    "batch_pipeline_v": (
        "mirror_batch_pipeline",
        BATCH_PIPELINE_COLUMNS,
        ("row_key",),
        (("stage_key",), ("material_no", "batch_no")),
    ),
    "weekly_metrics_v": (
        "mirror_weekly_metrics",
        (("metric_id", TEXT), ("week_start", DATE), ("completed", INTEGER), ("on_time", INTEGER),
         ("pct", PCT), ("run_id", TEXT)),
        ("metric_id", "week_start"),
        (),
    ),
    "weekly_metric_rows_v": (
        "mirror_weekly_metric_rows",
        (("metric_id", TEXT), ("week_start", DATE), ("row_key", TEXT), ("entry_date", DATE),
         ("exit_date", DATE), ("duration_days", INTEGER), ("sla_days", INTEGER), ("on_time", BOOLEAN),
         ("run_id", TEXT)),
        ("metric_id", "week_start", "row_key"),
        (("row_key",),),
    ),
    "pipeline_status_v": (
        "mirror_pipeline_status",
        (("last_run_id", TEXT), ("started_at", TIMESTAMP), ("last_success_at", TIMESTAMP),
         ("row_count", INTEGER), ("source_freshness_json", JSON)),
        ("last_run_id",),
        (),
    ),
    "stage_reference_v": (
        "mirror_stage_reference",
        (("stage_key", TEXT), ("label", TEXT), ("sort", INTEGER), ("sla_days", INTEGER),
         ("reeval_sla_days", INTEGER), ("team", TEXT), ("action", TEXT), ("terminal", BOOLEAN),
         ("show_card", BOOLEAN)),
        ("stage_key",),
        (),
    ),
    "metric_reference_v": (
        "mirror_metric_reference",
        (("metric_id", TEXT), ("label", TEXT), ("stage_key", TEXT), ("sla_days", INTEGER),
         ("computed_in", TEXT), ("status", TEXT), ("null_reason", TEXT)),
        ("metric_id",),
        (),
    ),
    "reason_codes_v": (
        "mirror_reason_codes",
        (("code", TEXT), ("label", TEXT)),
        ("code",),
        (),
    ),
    "deviations_v": (
        "mirror_deviations",
        (("deviation_no", TEXT), ("material_no", TEXT), ("batch_no", TEXT), ("title", TEXT),
         ("severity", TEXT), ("status", TEXT), ("opened_on", DATE), ("closed_on", DATE),
         ("root_cause_category", TEXT), ("owner", TEXT)),
        ("deviation_no", "material_no", "batch_no"),
        (("material_no", "batch_no"),),
    ),
    "expected_deliveries_v": (
        "mirror_expected_deliveries",
        (("ebeln", TEXT), ("ebelp", TEXT), ("material_no", TEXT), ("material_desc", TEXT),
         ("molecule_type", TEXT), ("material_class", TEXT), ("supplier_id", TEXT), ("supplier_name", TEXT),
         ("campaign", TEXT), ("scheduled_date", DATE), ("quantity", QUANTITY), ("planned_location", TEXT),
         ("planned_location_type", TEXT), ("overdue", BOOLEAN), ("run_id", TEXT)),
        ("ebeln", "ebelp"),
        (("material_no",),),
    ),
}  # fmt: skip

MIRROR_TABLES: dict[str, Table] = {}
for _object, (_table, _columns, _primary_key, _indexes) in MIRRORS.items():
    MIRROR_TABLES[_object] = Table(
        _table,
        Base.metadata,
        *(Column(name, kind, primary_key=name in _primary_key, nullable=name not in _primary_key)
          for name, kind in _columns),
        Column("contract_run_id", Text, nullable=False),
        Column("mirrored_at", STAMP, nullable=False),
        *(Index(f"ix_{_table}_{'_'.join(index)}", *index) for index in _indexes),
    )  # fmt: skip

# Objects whose rows carry a `run_id` column (checked against the status for a mixed publish, F08-FR-10).
OBJECTS_WITH_RUN_ID = tuple(
    name for name, (_, columns, _, _) in MIRRORS.items() if any(c == "run_id" for c, _ in columns)
)
