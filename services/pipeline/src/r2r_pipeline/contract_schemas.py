"""The Arrow schema of every published object: the types behind the Schema Reference page (F21-FR-06).

``tools/contract_schema.py`` turns these (plus the descriptions of ``specs/``) into ``specs/contract.json``.
A pipeline test publishes a run and checks that every Delta table has exactly the schema declared here, so
the types on the page cannot drift from what the pipeline writes (OQ-132).
"""

import pyarrow as pa

from r2r_pipeline.metrics import MONTHLY_METRICS_SCHEMA, WEEKLY_METRIC_ROWS_SCHEMA, WEEKLY_METRICS_SCHEMA
from r2r_pipeline.publish import (
    INBOUND_CHECKS_SCHEMA,
    PUBLISH_ORDER,
    SAMPLES_SCHEMA,
    STAGE_COLUMNS,
)
from r2r_pipeline.reports import PIPELINE_DAILY_SCHEMA, RELEASES_WEEKLY_SCHEMA
from r2r_pipeline.runs import PIPELINE_RUN_STEPS_SCHEMA, PIPELINE_RUNS_SCHEMA
from r2r_pipeline.schemas import BATCH_FLAT_SCHEMA, EXPECTED_DELIVERIES_SCHEMA

TEXT, DATE, BOOL, INT = pa.string(), pa.date32(), pa.bool_(), pa.int64()
STAMP = pa.timestamp("us", tz="UTC")

# The columns batch_pipeline_v adds to the batch_flat ones (04 section 4.1), in contract order.
_STAGE_TYPES: dict[str, pa.DataType] = {
    "stage_key": TEXT, "stage_rule_id": TEXT, "cycle_start_date": DATE, "ud_effective": BOOL,
    "stage_sort": pa.int32(), "current_stage_entry_date": DATE, "lims_rejected": BOOL,
    "receipt_entry": DATE, "receipt_exit": DATE, "call_off_entry": DATE, "call_off_exit": DATE,
    "sampling_entry": DATE, "sampling_exit": DATE, "qc_ship_entry": DATE, "qc_ship_exit": DATE,
    "qc_testing_entry": DATE, "qc_testing_exit": DATE, "qa_release_entry": DATE, "qa_release_exit": DATE,
    "applicable_sla_json": TEXT, "source_refs_json": TEXT, "system_need_by_locked": DATE, "on_hold": BOOL,
    "erp_blocked": BOOL, "re_eval": BOOL, "offsite": BOOL, "full_spec": BOOL, "ud_rejected": BOOL,
    "deviation_light": TEXT, "inbound_light": TEXT,
}  # fmt: skip

BATCH_PIPELINE_SCHEMA = pa.schema(
    [
        *BATCH_FLAT_SCHEMA,
        *((name, _STAGE_TYPES[name]) for name in STAGE_COLUMNS),
        ("snapshot_date", DATE),
        ("run_id", TEXT),
        ("published_at", STAMP),
    ]
)


def _text(*names: str) -> list[tuple[str, pa.DataType]]:
    return [(name, TEXT) for name in names]


_SCHEMAS: dict[str, pa.Schema] = {
    "batch_pipeline_v": BATCH_PIPELINE_SCHEMA,
    "weekly_metrics_v": WEEKLY_METRICS_SCHEMA,
    "weekly_metric_rows_v": WEEKLY_METRIC_ROWS_SCHEMA,
    "stage_reference_v": pa.schema(
        [
            *_text("stage_key", "label"),
            ("sort", INT),
            ("sla_days", INT),
            ("reeval_sla_days", INT),
            *_text("team", "action"),
            ("terminal", BOOL),
            ("show_card", BOOL),
        ]
    ),
    "metric_reference_v": pa.schema(
        [
            *_text("metric_id", "label", "stage_key"),
            ("sla_days", INT),
            *_text("computed_in", "status", "null_reason"),
        ]
    ),
    "reason_codes_v": pa.schema(_text("code", "label")),
    "deviations_v": pa.schema(
        [
            *_text("deviation_no", "material_no", "batch_no", "title", "severity", "status"),
            ("opened_on", DATE),
            ("closed_on", DATE),
            *_text(
                "root_cause_category",
                "causal_factor",
                "investigation_summary",
                "description",
                "owner",
                "run_id",
            ),
        ]
    ),
    "expected_deliveries_v": pa.schema([*EXPECTED_DELIVERIES_SCHEMA, ("run_id", TEXT)]),
    "inbound_checks_v": INBOUND_CHECKS_SCHEMA,
    "change_controls_v": pa.schema(
        [
            *_text("cc_no", "material_no", "batch_no", "title", "status", "current_state", "proposed_state"),
            ("opened_on", DATE),
            ("effective_on", DATE),
            ("run_id", TEXT),
        ]
    ),
    "samples_v": SAMPLES_SCHEMA,
    "monthly_metrics_v": MONTHLY_METRICS_SCHEMA,
    "pipeline_daily_v": PIPELINE_DAILY_SCHEMA,
    "releases_weekly_v": RELEASES_WEEKLY_SCHEMA,
    "pipeline_runs_v": PIPELINE_RUNS_SCHEMA,
    "pipeline_run_steps_v": PIPELINE_RUN_STEPS_SCHEMA,
    "pipeline_status_v": pa.schema(
        [
            ("last_run_id", TEXT),
            ("started_at", STAMP),
            ("last_success_at", STAMP),
            ("row_count", INT),
            ("source_freshness_json", TEXT),
        ]
    ),
}


def published_schemas() -> dict[str, pa.Schema]:
    """Every published object's schema, in publish order."""
    return {name: _SCHEMAS[name] for name in PUBLISH_ORDER}
