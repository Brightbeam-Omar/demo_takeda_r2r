"""Helpers for the stage-engine tests: hand-built ``batch_flat`` rows run through the SQL steps 50-90."""

from datetime import date
from pathlib import Path
from typing import Any

import duckdb
import pyarrow as pa
from r2r_core.profile import SiteProfile
from r2r_pipeline.context import new_context
from r2r_pipeline.schemas import BATCH_FLAT_SCHEMA
from r2r_pipeline.transform import run_files

TODAY = date(2026, 10, 12)
D = date

DEFAULTS: dict[str, Any] = {
    "material_no": "RM1", "material_desc": "Excipient 001", "material_class": "drug_substance",
    "molecule_type": "small_molecule", "supplier_id": "SUP1", "supplier_name": "Supplier 001",
    "supplier_batch": "B1", "batch_no": "B1", "batch_status_code": "", "inspection_lot_no": "10000001",
    "lot_type": "01", "lot_start_date": D(2026, 9, 1), "storage_location": "0100", "location_type": "onsite",
    "received_location_type": "onsite", "stock_category": "QI", "gr_date": D(2026, 9, 1),
    "transfer_to_site_date": None, "inbound_check_status": "passed",
    "inbound_check_completed_date": D(2026, 9, 3), "sample_id": None, "sample_collected_date": None,
    "offsite_test": False, "external_lab": None, "sample_shipped_date": None, "lims_status": "none",
    "lims_approved_date": None, "lims_approved_at": None, "ud_code": None, "ud_date": None,
    "erp_results_recorded_at": None, "campaign": None, "system_need_by_date": None,
    "open_deviation_count": 0, "closed_deviation_count": 0, "next_inspection_date": None,
    "need_by_at_release": None, "expedite_requested_on": None, "expedite_due_date": None,
}  # fmt: skip


def flat_row(lot: str = "10000001", **values: Any) -> dict[str, Any]:
    row = {**DEFAULTS, "inspection_lot_no": lot, **values}
    row["row_key"] = f"{row['material_no']}|{row['batch_no']}|{lot}"
    return row


def run_engine(rows: list[dict[str, Any]], profile: SiteProfile, tmp_path: Path) -> dict[str, dict[str, Any]]:
    """Run the stage engine and flags SQL on ``rows``; returns ``{row_key: engine output row}``."""
    connection = duckdb.connect()
    connection.register("batch_flat", pa.Table.from_pylist(rows, schema=BATCH_FLAT_SCHEMA))
    ctx = new_context(profile, tmp_path, snapshot_date=TODAY)
    run_files(connection, ctx, lambda path: path.name[:2] >= "50" or path.name.startswith("60"))
    result = connection.execute("SELECT * FROM batch_stage_sql").to_arrow_table().to_pylist()
    return {row["row_key"]: row for row in result}
