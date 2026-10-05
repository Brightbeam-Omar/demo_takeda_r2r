"""Explain payloads (F09-FR-06): why a row is in a stage, how its date was planned, where a figure came from.

Nothing is recomputed here. The stage comes from the published ``stage_rule_id`` and the rule's own
inputs, the plan from ``r2r_core.sla`` through ``compose``, and metric figures from the contributing
rows the pipeline published (``mirror_weekly_metric_rows``).
"""

import datetime as dt
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel
from r2r_core.profile import SiteProfile
from r2r_core.sla import sla_for
from r2r_core.stage_rules import RULES, StageRule

from app_api.schemas import Freshness
from app_api.services.compose import ComposedRow


class RuleOut(BaseModel):
    id: str
    stage_key: str
    condition_sql: str
    description: str
    inputs: list[str]

    @classmethod
    def of(cls, rule: StageRule) -> "RuleOut":
        return cls(
            id=rule.id,
            stage_key=rule.stage_key,
            condition_sql=rule.condition_sql,
            description=rule.description,
            inputs=list(rule.inputs),
        )


class StageExplain(BaseModel):
    kind: Literal["stage"] = "stage"
    row_key: str
    stage_key: str
    stage_label: str
    rule: RuleOut
    input_values: dict[str, Any]
    source_refs: Any
    freshness: Freshness


class CompletionExplain(BaseModel):
    kind: Literal["expected_completion"] = "expected_completion"
    row_key: str
    stage_key: str
    entry_date: dt.date | None
    system_need_by: dt.date | None
    operative_need_by: dt.date | None
    need_by_adjusted: bool
    adjusted_reason_code: str | None
    applicable_slas: Any
    base_slas: dict[str, int]
    effective_slas: dict[str, int]
    available_days: int | None
    budget_days: int | None
    compressed: bool
    compression_ratio: Decimal | None
    must_complete_by: dict[str, dt.date]
    expected_completion: dt.date | None
    days_remaining: int | None
    rag: str | None
    formula: str
    freshness: Freshness


class MetricRowOut(BaseModel):
    row_key: str
    entry_date: dt.date | None
    exit_date: dt.date | None
    duration_days: int | None
    sla_days: int | None
    on_time: bool | None


class MetricExplain(BaseModel):
    kind: Literal["metric"] = "metric"
    metric_id: str
    label: str
    status: str
    null_reason: str | None
    week_start: dt.date | None
    completed: int | None
    on_time: int | None
    pct: Decimal | None
    sla_days: int | None
    rows: list[MetricRowOut]
    freshness: Freshness


class FlowExplain(BaseModel):
    kind: Literal["flow"] = "flow"
    stage_key: str
    stage_label: str
    count: int
    breached: bool
    mode: Literal["snapshot", "due_in_period"]
    filters: dict[str, Any]
    rules: list[RuleOut]
    row_keys: list[str]
    freshness: Freshness


def explain_stage(row: ComposedRow, profile: SiteProfile, fresh: Freshness) -> StageExplain:
    facts = row.facts
    rule = next(rule for rule in RULES if rule.id == facts["stage_rule_id"])
    return StageExplain(
        row_key=row.row_key,
        stage_key=facts["stage_key"],
        stage_label=profile.stage(facts["stage_key"]).label,
        rule=RuleOut.of(rule),
        input_values={column: facts[column] for column in rule.inputs},
        source_refs=facts["source_refs_json"],
        freshness=fresh,
    )


def _formula(row: ComposedRow, available: int | None, budget: int | None) -> str:
    plan = row.plan
    entry = row.facts["current_stage_entry_date"]
    if plan.expected_completion is None:
        return "No expected completion: this stage takes no part in the SLA plan."
    if row.operative_need_by is None:
        return (
            f"No need-by date, so the plan runs forward from the stage entry date ({entry}): each remaining "
            f"stage ends after its SLA days."
        )
    base = f"Backward from the need-by date ({row.operative_need_by}): the last stage ends on it"
    if available is not None and budget is not None and available <= 0:
        return (
            f"{base}, but it is on or before the stage entry date ({entry}). Every remaining stage is "
            f"compressed to 1 day and the row is already late."
        )
    if plan.compressed:
        return (
            f"{base}. Available time {available} days is less than the SLA budget {budget} days, so each "
            f"SLA is scaled by {available}/{budget} (rounded half up, minimum 1 day)."
        )
    return (
        f"{base}. Available time {available} days covers the SLA budget {budget} days, so the full "
        f"SLAs apply and each earlier stage must finish by the next one's start."
    )


def explain_completion(row: ComposedRow, profile: SiteProfile, fresh: Freshness) -> CompletionExplain:
    plan = row.plan
    entry = row.facts["current_stage_entry_date"]
    base = {str(stage): sla_for(stage, row.row_facts.lot_type, profile) for stage in plan.effective_slas}
    need_by = row.operative_need_by
    available = (need_by - entry).days if need_by is not None and entry is not None else None
    budget = sum(base.values()) if base else None
    return CompletionExplain(
        row_key=row.row_key,
        stage_key=row.facts["stage_key"],
        entry_date=entry,
        system_need_by=row.facts["system_need_by_locked"],
        operative_need_by=need_by,
        need_by_adjusted=row.adjusted is not None,
        adjusted_reason_code=row.adjusted.reason_code if row.adjusted else None,
        applicable_slas=row.facts["applicable_sla_json"],
        base_slas=base,
        effective_slas={str(k): v for k, v in plan.effective_slas.items()},
        available_days=available,
        budget_days=budget,
        compressed=plan.compressed,
        compression_ratio=plan.compression_ratio,
        must_complete_by={str(k): v for k, v in plan.must_complete_by.items()},
        expected_completion=plan.expected_completion,
        days_remaining=plan.days_remaining,
        rag=plan.rag.value if plan.rag else None,
        formula=_formula(row, available, budget),
        freshness=fresh,
    )
