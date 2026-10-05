"""Response models of the read API (F09-FR-01, FR-07). They are the source of the generated OpenAPI schema."""

import datetime as dt
from decimal import Decimal
from typing import Any

from pydantic import BaseModel
from r2r_core.sla import PlanResult

from app_api.services.compose import ComposedRow


class Freshness(BaseModel):
    """Which contract run the answer is built from, and how old it is on the demo clock (F09-FR-07)."""

    contract_run_id: str | None
    last_success_at: dt.datetime | None
    freshness_minutes: int | None


class PlanOut(BaseModel):
    expected_completion: dt.date | None
    must_complete_by: dict[str, dt.date]
    effective_slas: dict[str, int]
    compressed: bool
    compression_ratio: Decimal | None
    days_in_stage: int | None
    days_remaining: int | None
    rag: str | None
    late: bool
    late_reason_auto: str | None

    @classmethod
    def of(cls, result: PlanResult) -> "PlanOut":
        return cls(
            expected_completion=result.expected_completion,
            must_complete_by={str(k): v for k, v in result.must_complete_by.items()},
            effective_slas={str(k): v for k, v in result.effective_slas.items()},
            compressed=result.compressed,
            compression_ratio=result.compression_ratio,
            days_in_stage=result.days_in_stage,
            days_remaining=result.days_remaining,
            rag=result.rag.value if result.rag else None,
            late=result.late,
            late_reason_auto=result.late_reason_auto,
        )


class FlagsOut(BaseModel):
    on_hold: bool
    erp_blocked: bool
    re_eval: bool
    offsite: bool
    full_spec: bool
    expedite: bool
    ud_rejected: bool
    lims_rejected: bool
    air_gap: bool
    late: bool


class RowOut(BaseModel):
    """One lot: the facts the table shows, the human input and the plan computed from both."""

    row_key: str
    material_no: str
    material_desc: str | None
    material_class: str | None
    molecule_type: str | None
    supplier_name: str | None
    batch_no: str
    inspection_lot_no: str
    lot_type: str
    campaign: str | None
    stage_key: str
    stage_label: str
    stage_rule_id: str | None
    current_stage_entry_date: dt.date | None
    lims_status: str | None
    ud_code: str | None
    system_need_by_locked: dt.date | None
    adjusted_need_by_date: dt.date | None
    adjusted_reason_code: str | None
    operative_need_by: dt.date | None
    expedite: bool
    manual_status: dict[str, Any] | None
    plan: PlanOut
    air_gap: bool
    air_gap_hours: int
    late: bool
    days_in_stage: int | None
    deviation_light: str | None
    inbound_light: str | None
    flags: FlagsOut
    comment_count: int

    @classmethod
    def of(cls, row: ComposedRow, stage_labels: dict[str, str]) -> "RowOut":
        facts = row.facts
        return cls(
            row_key=row.row_key,
            material_no=facts["material_no"],
            material_desc=facts["material_desc"],
            material_class=facts["material_class"],
            molecule_type=facts["molecule_type"],
            supplier_name=facts["supplier_name"],
            batch_no=facts["batch_no"],
            inspection_lot_no=facts["inspection_lot_no"],
            lot_type=facts["lot_type"],
            campaign=facts["campaign"],
            stage_key=facts["stage_key"],
            stage_label=stage_labels.get(facts["stage_key"], facts["stage_key"]),
            stage_rule_id=facts["stage_rule_id"],
            current_stage_entry_date=facts["current_stage_entry_date"],
            lims_status=facts["lims_status"],
            ud_code=facts["ud_code"],
            system_need_by_locked=facts["system_need_by_locked"],
            adjusted_need_by_date=row.adjusted.date if row.adjusted else None,
            adjusted_reason_code=row.adjusted.reason_code if row.adjusted else None,
            operative_need_by=row.operative_need_by,
            expedite=row.expedite,
            manual_status=dict(row.manual_status) if row.manual_status else None,
            plan=PlanOut.of(row.plan),
            air_gap=row.air_gap,
            air_gap_hours=row.air_gap_hours,
            late=row.plan.late,
            days_in_stage=row.plan.days_in_stage,
            deviation_light=facts["deviation_light"],
            inbound_light=facts["inbound_light"],
            flags=FlagsOut(
                on_hold=bool(facts["on_hold"]),
                erp_blocked=bool(facts["erp_blocked"]),
                re_eval=bool(facts["re_eval"]),
                offsite=bool(facts["offsite"]),
                full_spec=bool(facts["full_spec"]),
                expedite=row.expedite,
                ud_rejected=bool(facts["ud_rejected"]),
                lims_rejected=bool(facts["lims_rejected"]),
                air_gap=row.air_gap,
                late=row.plan.late,
            ),
            comment_count=row.comment_count,
        )


class OverrideOut(BaseModel):
    id: int
    field: str
    value: Any
    reason_code: str | None
    note: str | None
    version: int
    author_user_key: str
    created_at: dt.datetime
    is_current: bool


class CommentOut(BaseModel):
    id: int
    row_key: str
    body: str
    author_user_key: str
    created_at: dt.datetime


class DeviationOut(BaseModel):
    deviation_no: str
    title: str | None
    severity: str | None
    status: str | None
    opened_on: dt.date | None
    closed_on: dt.date | None
    root_cause_category: str | None
    owner: str | None


class RowDetail(RowOut):
    """``GET /api/rows/{row_key}``: the row with every mirror column, its overrides, comments and siblings."""

    freshness: Freshness
    facts: dict[str, Any]
    current_overrides: dict[str, OverrideOut]
    override_history: list[OverrideOut]
    comments: list[CommentOut]
    deviations: list[DeviationOut]
    siblings: list[RowOut]
