"""``applicable_sla_json``: the ordered stages a row passes through and their SLA days (F06-FR-05).

The logic is ``r2r_core.sla`` (``applicable_stages`` honours the profile's ``applies_if``, ``sla_for`` its
re-evaluation overrides). The pipeline does not repeat it (constitution P2, OQ-042).
"""

import json

import pyarrow as pa
from r2r_core.domain import LotType, RowFacts, StageKey
from r2r_core.profile import SiteProfile
from r2r_core.sla import applicable_stages, sla_for


def build_applicable_sla(flat: pa.Table, stage: pa.Table, profile: SiteProfile) -> dict[str, str]:
    """``{row_key: json}`` for every row of ``batch_flat``, using the stage from ``batch_stage``."""
    stage_of = dict(zip(stage["row_key"].to_pylist(), stage["stage_key"].to_pylist(), strict=True))
    columns = ["row_key", "lot_type", "received_location_type", "offsite_test", "lims_status", "ud_code"]
    out: dict[str, str] = {}
    for row in flat.select(columns).to_pylist():
        facts = RowFacts(
            row_key=row["row_key"],
            stage_key=StageKey(stage_of[row["row_key"]]),
            lot_type=LotType(row["lot_type"]),
            received_location_type=row["received_location_type"] or "",
            offsite=bool(row["offsite_test"]),
            current_stage_entry_date=None,
            system_need_by_locked=None,
            on_hold=False,
            ud_rejected=False,
            lims_status=row["lims_status"],
            ud_effective=False,
            ud_code=row["ud_code"],
            lims_approved_at=None,
        )
        items = [
            {"stage_key": key, "sla_days": sla_for(key, facts.lot_type, profile)}
            for key in applicable_stages(facts, profile)
        ]
        out[row["row_key"]] = json.dumps(items, separators=(",", ":"))
    return out
