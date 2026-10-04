"""Renders the stage engine SQL from the profile and the rule list (F06-FR-04).

``50_stage.sql.j2`` is a template; this module gives it the rules (``r2r_core.stage_rules``), the per-stage
entry and exit date expressions and the stage order. Stage SLAs never appear here: they are used only through
``r2r_core.sla`` (see ``applicable_sla.py``).
"""

from typing import Any

from r2r_core.applies_if import ALIASES, parse_applies_if
from r2r_core.profile import SiteProfile
from r2r_core.stage_rules import RULES, check_rules

# Entry and exit date of each stage (03-domain-model section 4). An earlier stage's exit is the column
# ``<stage>_exit`` the engine builds, so stages are rendered in profile order.
STAGE_DATES: dict[str, tuple[str, str]] = {
    "receipt": (
        "cycle_start_date",
        "COALESCE(inbound_check_completed_date, "
        "CASE WHEN inbound_check_status = 'none' THEN cycle_start_date END)",
    ),
    "call_off": ("receipt_exit", "transfer_to_site_date"),
    "sampling": (
        "CASE WHEN received_location_type = '3pl' THEN transfer_to_site_date ELSE receipt_exit END",
        "sample_collected_date",
    ),
    "qc_ship": ("sample_collected_date", "sample_shipped_date"),
    "qc_testing": (
        "CASE WHEN offsite_test THEN sample_shipped_date ELSE sample_collected_date END",
        "CASE WHEN lims_status = 'approved' THEN lims_approved_date END",
    ),
    "qa_release": (
        "CASE WHEN lims_status = 'approved' THEN lims_approved_date END",
        "CASE WHEN ud_effective THEN ud_date END",
    ),
}

COLUMN_FOR_FIELD = {**{alias: alias for alias in ALIASES}, "offsite": "offsite_test"}
SUPPORTED_FIELDS = {"received_location_type", "lot_type", "lims_status", "ud_code", "offsite", "ud_effective"}


def applies_sql(expression: str) -> str:
    """The profile's ``applies_if`` condition as SQL over the engine's columns."""
    condition = parse_applies_if(expression)
    if condition.field not in SUPPORTED_FIELDS:
        raise ValueError(f"applies_if field {condition.field!r} is not available to the stage engine")
    column = COLUMN_FOR_FIELD.get(condition.field, condition.field)
    if condition.literal is None:
        return column
    return f"{column} = '{condition.literal.replace(chr(39), chr(39) * 2)}'"


def engine_variables(profile: SiteProfile) -> dict[str, Any]:
    """Template variables of the stage engine SQL files."""
    check_rules(profile)
    dated = []
    for stage in profile.stages:
        if stage.key not in STAGE_DATES:
            continue
        entry, exit_ = STAGE_DATES[stage.key]
        if stage.applies_if:
            gate = applies_sql(stage.applies_if)
            entry, exit_ = f"CASE WHEN {gate} THEN {entry} END", f"CASE WHEN {gate} THEN {exit_} END"
        dated.append({"key": stage.key, "entry": entry, "exit": exit_})
    return {
        "rules": [{"id": r.id, "stage_key": r.stage_key, "condition": r.condition_sql} for r in RULES],
        "dated_stages": dated,
        "stage_sort": [(stage.key, number) for number, stage in enumerate(profile.stages, start=1)],
    }
