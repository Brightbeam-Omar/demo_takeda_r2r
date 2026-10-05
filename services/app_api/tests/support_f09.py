"""Fixtures for the F09 tests: mirror rows with every column, and a loader for the mirror tables."""

from datetime import UTC, date, datetime
from typing import Any

from app_api.models import MIRRORS
from r2r_core.profile import SiteProfile
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

NOW = datetime(2026, 10, 12, 7, 0, tzinfo=UTC)
RUN = "run-1"
OBJECT_TABLES = [table for table, *_ in MIRRORS.values()]


def D(month: int, day: int, year: int = 2026) -> date:
    return date(year, month, day)


def blank(name: str) -> dict[str, Any]:
    return {column: None for column, _ in MIRRORS[name][1]}


def batch(
    batch_no: str = "B2077", material: str = "RM10031", lot: str = "9001", **over: Any
) -> dict[str, Any]:
    """An onsite initial lot in sampling since 8 Oct with a locked need-by of 3 Dec (the B2077 story)."""
    row = blank("batch_pipeline_v") | {
        "row_key": f"{material}|{batch_no}|{lot}",
        "material_no": material,
        "material_desc": f"Material {material}",
        "material_class": "drug_substance",
        "molecule_type": "small_molecule",
        "supplier_id": "SUP007",
        "supplier_name": "Supplier 7",
        "batch_no": batch_no,
        "inspection_lot_no": lot,
        "lot_type": "01",
        "received_location_type": "onsite",
        "inbound_check_status": "passed",
        "lims_status": "none",
        "campaign": "CMP-BRAVO",
        "stage_key": "sampling",
        "stage_rule_id": "R-SMP",
        "cycle_start_date": D(10, 2),
        "ud_effective": False,
        "stage_sort": 3,
        "current_stage_entry_date": D(10, 8),
        "sampling_entry": D(10, 8),
        "applicable_sla_json": {},
        "source_refs_json": {},
        "system_need_by_date": D(12, 3),
        "system_need_by_locked": D(12, 3),
        "on_hold": False,
        "erp_blocked": False,
        "re_eval": False,
        "offsite": False,
        "full_spec": False,
        "ud_rejected": False,
        "lims_rejected": False,
        "deviation_light": "none",
        "inbound_light": "none",
        "open_deviation_count": 0,
        "closed_deviation_count": 0,
        "snapshot_date": D(10, 12),
        "run_id": RUN,
        "published_at": NOW,
    }
    return row | over


def stage_reference(profile: SiteProfile) -> list[dict[str, Any]]:
    return [
        {
            "stage_key": s.key,
            "label": s.label,
            "sort": index,
            "sla_days": s.sla_days,
            "reeval_sla_days": profile.reeval_sla_overrides.get(s.key),
            "team": s.team,
            "action": s.action,
            "terminal": s.terminal,
        }
        for index, s in enumerate(profile.stages)
    ]


def metric_reference(profile: SiteProfile) -> list[dict[str, Any]]:
    return [
        {
            "metric_id": m.id,
            "label": m.label,
            "stage_key": m.stage,
            "sla_days": m.sla_days,
            "computed_in": m.computed_in,
            "status": "active" if m.computed_in == "pipeline" else "awaiting_signal",
            "null_reason": m.null_reason,
        }
        for m in profile.metrics
    ]


def load_mirror(
    factory: sessionmaker[Session],
    profile: SiteProfile,
    rows: list[dict[str, Any]],
    *,
    run_id: str = RUN,
    metrics: list[dict[str, Any]] | None = None,
    metric_rows: list[dict[str, Any]] | None = None,
    deviations: list[dict[str, Any]] | None = None,
) -> None:
    """Replace the mirror tables with ``rows`` and the profile's reference data."""
    data: dict[str, list[dict[str, Any]]] = {
        "batch_pipeline_v": rows,
        "weekly_metrics_v": metrics or [],
        "weekly_metric_rows_v": metric_rows or [],
        "pipeline_status_v": [
            {
                "last_run_id": run_id,
                "started_at": NOW,
                "last_success_at": NOW,
                "row_count": len(rows),
                "source_freshness_json": {},
            }
        ],
        "stage_reference_v": stage_reference(profile),
        "metric_reference_v": metric_reference(profile),
        "reason_codes_v": [{"code": c, "label": c.replace("_", " ").title()} for c in profile.reason_codes],
        "deviations_v": deviations or [],
    }
    with factory() as session:
        for name, (table, columns, _, _) in MIRRORS.items():
            session.execute(text(f"DELETE FROM {table}"))
            for record in data[name]:
                values = {c: record.get(c) for c, _ in columns} | {
                    "contract_run_id": run_id,
                    "mirrored_at": NOW,
                }
                names = ", ".join(values)
                marks = ", ".join(
                    f":{k}" if k not in JSON_COLUMNS else f"CAST(:{k} AS jsonb)" for k in values
                )
                session.execute(text(f"INSERT INTO {table} ({names}) VALUES ({marks})"), _encode(values))
        session.commit()


JSON_COLUMNS = {"applicable_sla_json", "source_refs_json", "source_freshness_json"}


def _encode(values: dict[str, Any]) -> dict[str, Any]:
    import json

    return {k: json.dumps(v) if k in JSON_COLUMNS and v is not None else v for k, v in values.items()}
