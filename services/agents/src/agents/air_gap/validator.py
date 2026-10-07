"""The deterministic validator V1-V6 (F12-FR-07, constitution P3). No model is involved.

Every rule always runs and gives pass or fail with a message; the result goes to ``validator_result_json``.
The validator **re-reads the sources itself** and never trusts what the agent saw, so V2 is independent
verification. V3 reuses ``r2r_core.airgap`` (the same function the pipeline's air-gap flag uses), V5's window
comes from the site profile, and the identifier patterns of V6 are written down here with a test against the
generated data.

| rule | checks |
|------|--------|
| V1 | the row exists and is still an air gap |
| V2 | every evidence item resolves, belongs to this batch, and its value matches the source |
| V3 | `hours_in_gap` is within one hour of the hours computed from the sources |
| V4 | `recommended_action` and `open_deviations` match QMS |
| V5 | `priority` is high exactly when the need-by is within the profile window, or the row is late |
| V6 | every batch, material, sample, lot and deviation id in the title or summary is in the evidence/row |
"""

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ValidationError
from r2r_core import clock
from r2r_core.airgap import air_gap

from agents.air_gap.evidence import EVIDENCE_FIELDS, NONE, normalise, parse_timestamp
from agents.air_gap.schema import AirGapTicket, EvidenceItem
from agents.tools.http import ReadOnlyHttp, ToolError
from agents.tools.sources import (
    fetch_deviation,
    fetch_deviations,
    fetch_erp_lot,
    fetch_lims_sample,
    fetch_row,
)

HOURS_TOLERANCE = 1

BATCH_PATTERN = re.compile(r"\bB\d{4}\b")
MATERIAL_PATTERN = re.compile(r"\b(?:RM|CN)\d{5}\b")
SAMPLE_PATTERN = re.compile(r"\bS-\d{7}\b")
LOT_PATTERN = re.compile(r"\b1\d{7}\b")
DEVIATION_PATTERN = re.compile(r"\bDEV-\d{6}\b")
IDENTIFIER_PATTERNS = (BATCH_PATTERN, MATERIAL_PATTERN, SAMPLE_PATTERN, LOT_PATTERN, DEVIATION_PATTERN)

RULES = {
    "V1": "Row is still an air gap",
    "V2": "Evidence matches the sources",
    "V3": "Hours in gap match",
    "V4": "Recommended action matches",
    "V5": "Priority matches",
    "V6": "Only known identifiers are cited",
}


class RuleResult(BaseModel):
    id: str
    name: str
    passed: bool
    message: str


class EvidenceCheck(BaseModel):
    index: int
    verified: bool
    message: str


class ValidatorResult(BaseModel):
    passed: bool
    headline: str | None
    rules: list[RuleResult]
    evidence: list[EvidenceCheck]
    checked_at: str


@dataclass
class ValidationContext:
    http: ReadOnlyHttp
    demo_user: str | None
    threshold_hours: int
    high_priority_days: int
    now: datetime
    today: date


def validate_payload(payload: dict[str, Any], context: ValidationContext) -> ValidatorResult:
    """Validate a stored ticket; a payload that does not match the schema fails as ``V0``."""
    try:
        ticket = AirGapTicket.model_validate(payload)
    except ValidationError as error:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in e['loc']) or 'output'}: {e['msg']}" for e in error.errors()
        )
        rules = [RuleResult(id="V0", name="Output matches the schema", passed=False, message=problems)]
        rules += [
            RuleResult(
                id=rule, name=name, passed=False, message="not run: the output did not match the schema"
            )
            for rule, name in RULES.items()
        ]
        return ValidatorResult(
            passed=False, headline=problems, rules=rules, evidence=[], checked_at=clock.now().isoformat()
        )
    return validate_ticket(ticket, context)


def validate_ticket(ticket: AirGapTicket, context: ValidationContext) -> ValidatorResult:
    row = _row(ticket, context)
    checks = _check_evidence(ticket, context, row)
    rules = [
        _v1(row, ticket),
        _v2(checks),
        _v3(ticket, context, row),
        _v4(ticket, context, row),
        _v5(ticket, context, row),
        _v6(ticket, row),
    ]
    failed = next((rule for rule in rules if not rule.passed), None)
    return ValidatorResult(
        passed=failed is None,
        headline=failed.message if failed else None,
        rules=rules,
        evidence=checks,
        checked_at=clock.now().isoformat(),
    )


def _row(ticket: AirGapTicket, context: ValidationContext) -> dict[str, Any] | None:
    try:
        return fetch_row(context.http, ticket.row_key, context.demo_user)
    except ToolError:
        return None


def _rule(rule: str, passed: bool, message: str) -> RuleResult:
    return RuleResult(id=rule, name=RULES[rule], passed=passed, message=message)


# --- V1 ---------------------------------------------------------------------------------------------


def _v1(row: dict[str, Any] | None, ticket: AirGapTicket) -> RuleResult:
    if row is None:
        return _rule("V1", False, f"Row {ticket.row_key} no longer exists")
    if not row["air_gap"]:
        return _rule("V1", False, "Air gap resolved")
    return _rule(
        "V1", True, f"Row {row['batch_no']} exists and is still an air gap ({row['air_gap_hours']} h)"
    )


# --- V2 ---------------------------------------------------------------------------------------------


def _check_evidence(
    ticket: AirGapTicket, context: ValidationContext, row: dict[str, Any] | None
) -> list[EvidenceCheck]:
    return [
        EvidenceCheck(index=i, **_check_item(item, context, row)) for i, item in enumerate(ticket.evidence)
    ]


def _check_item(item: EvidenceItem, context: ValidationContext, row: dict[str, Any] | None) -> dict[str, Any]:
    if item.field not in EVIDENCE_FIELDS[item.system]:
        return {"verified": False, "message": f"unknown evidence field {item.system}.{item.field}"}
    try:
        actual, batch_ok = _read_record(item, context, row)
    except ToolError as error:
        return {"verified": False, "message": str(error)}
    if not batch_ok:
        return {"verified": False, "message": f"{item.ref} belongs to another batch than this row"}
    if normalise(item.value) != normalise(actual):
        return {
            "verified": False,
            "message": f"{item.field} of {item.ref} is {normalise(actual)}, the ticket says {item.value}",
        }
    return {"verified": True, "message": f"{item.field} of {item.ref} is {normalise(actual)}"}


def _read_record(
    item: EvidenceItem, context: ValidationContext, row: dict[str, Any] | None
) -> tuple[Any, bool]:
    """Read the record again from its source: the field's value, and whether the record is this row's."""
    batch = row["batch_no"] if row else None
    if item.system == "LIMS":
        sample = fetch_lims_sample(context.http, item.ref)
        return sample[item.field], batch is not None and sample["batch_no"] == batch
    if item.system == "ERP":
        lot = fetch_erp_lot(context.http, item.ref)
        return lot[item.field], batch is not None and lot["batch_no"] == batch
    deviation = fetch_deviation(context.http, item.ref)
    linked = batch is not None and any(
        d["deviation_no"] == item.ref for d in fetch_deviations(context.http, batch)
    )
    return deviation[item.field], linked


def _v2(checks: list[EvidenceCheck]) -> RuleResult:
    bad = [c for c in checks if not c.verified]
    if bad:
        return _rule(
            "V2", False, f"{len(bad)} of {len(checks)} evidence items do not verify: {bad[0].message}"
        )
    return _rule("V2", True, f"All {len(checks)} evidence items match the sources")


# --- V3 ---------------------------------------------------------------------------------------------


def _computed_hours(context: ValidationContext, row: dict[str, Any]) -> int:
    sample = fetch_lims_sample(context.http, row["sample_id"])
    lot = fetch_erp_lot(context.http, row["inspection_lot_no"])
    recorded = parse_timestamp(lot["results_recorded_at"]) if lot["results_recorded_at"] else None
    approved = parse_timestamp(sample["approved_at"]) if sample["approved_at"] else None
    _, hours = air_gap(
        sample["status"], lot["ud_code"], approved, context.now, context.threshold_hours, recorded
    )
    return hours


def _v3(ticket: AirGapTicket, context: ValidationContext, row: dict[str, Any] | None) -> RuleResult:
    if row is None or not row.get("sample_id"):
        return _rule("V3", False, "Hours cannot be computed: the row or its sample is unavailable")
    try:
        hours = _computed_hours(context, row)
    except ToolError as error:
        return _rule("V3", False, f"Hours cannot be computed: {error}")
    if abs(ticket.hours_in_gap - hours) > HOURS_TOLERANCE:
        return _rule(
            "V3", False, f"Ticket says {ticket.hours_in_gap} h in the gap, the sources give {hours} h"
        )
    return _rule(
        "V3", True, f"{ticket.hours_in_gap} h is within {HOURS_TOLERANCE} h of the computed {hours} h"
    )


# --- V4 ---------------------------------------------------------------------------------------------


def _v4(ticket: AirGapTicket, context: ValidationContext, row: dict[str, Any] | None) -> RuleResult:
    if row is None:
        return _rule("V4", False, "Deviations cannot be read: the row is unavailable")
    try:
        deviations = fetch_deviations(context.http, row["batch_no"])
    except ToolError as error:
        return _rule("V4", False, f"Deviations cannot be read: {error}")
    open_numbers = sorted(d["deviation_no"] for d in deviations if d["status"] == "open")
    expected = "investigate_deviation_first" if open_numbers else "post_usage_decision"
    if ticket.recommended_action != expected:
        reason = f"open deviations {', '.join(open_numbers)}" if open_numbers else "no open deviations"
        return _rule(
            "V4",
            False,
            f"Action should be {expected} ({reason}), the ticket says {ticket.recommended_action}",
        )
    if sorted(ticket.open_deviations) != open_numbers:
        return _rule(
            "V4",
            False,
            f"Open deviations are {', '.join(open_numbers) or 'none'}, the ticket lists "
            f"{', '.join(sorted(ticket.open_deviations)) or 'none'}",
        )
    return _rule("V4", True, f"{expected} matches QMS ({len(open_numbers)} open deviation(s))")


# --- V5 ---------------------------------------------------------------------------------------------


def _v5(ticket: AirGapTicket, context: ValidationContext, row: dict[str, Any] | None) -> RuleResult:
    if row is None:
        return _rule("V5", False, "Priority cannot be checked: the row is unavailable")
    need_by = row.get("operative_need_by")
    days = (date.fromisoformat(need_by) - context.today).days if need_by else None
    high = bool(row["late"]) or (days is not None and days <= context.high_priority_days)
    expected = "high" if high else "normal"
    why = (
        "the row is late"
        if row["late"]
        else "no need-by date"
        if days is None
        else f"need-by is {days} days away, the window is {context.high_priority_days} days"
    )
    if ticket.priority != expected:
        return _rule("V5", False, f"Priority should be {expected} ({why}), the ticket says {ticket.priority}")
    return _rule("V5", True, f"Priority {expected} matches ({why})")


# --- V6 ---------------------------------------------------------------------------------------------


def _v6(ticket: AirGapTicket, row: dict[str, Any] | None) -> RuleResult:
    known = " ".join(f"{i.ref} {i.value}" for i in ticket.evidence)
    known += f" {ticket.row_key}"
    if row:
        known += " " + " ".join(str(v) for v in row.values() if v is not None)
    text = f"{ticket.title} {ticket.summary}"
    unknown = sorted(
        {m for pattern in IDENTIFIER_PATTERNS for m in pattern.findall(text) if m not in _words(known)}
    )
    if unknown:
        return _rule("V6", False, f"Not in the evidence or the row: {', '.join(unknown)}")
    return _rule("V6", True, "Every identifier in the title and summary is in the evidence or the row")


def _words(text: str) -> set[str]:
    return set(re.findall(r"[A-Za-z0-9-]+", text.replace("|", " ")))


__all__ = ["NONE", "ValidationContext", "ValidatorResult", "validate_payload", "validate_ticket"]
