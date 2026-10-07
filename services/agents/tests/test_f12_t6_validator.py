"""F12 T6 [TDD]: AirGapTicket schema and validator rules V1-V6 [F12-FR-06, F12-FR-07, F12-AC-03, F12-AC-04]."""

import re
from datetime import date
from typing import Any

import pytest
from agent_support import OPEN_DEVIATION, ROW_KEY, evidence, row_body, source_transport, ticket
from agents.air_gap.schema import EvidenceItem
from agents.air_gap.validator import (
    BATCH_PATTERN,
    DEVIATION_PATTERN,
    LOT_PATTERN,
    MATERIAL_PATTERN,
    SAMPLE_PATTERN,
    ValidationContext,
    validate_payload,
    validate_ticket,
)
from agents.settings import Settings
from agents.tools.http import ReadOnlyHttp
from pydantic import ValidationError
from r2r_core.clock import now as demo_now


def context(**transport: Any) -> ValidationContext:
    http = ReadOnlyHttp.from_settings(Settings.from_env({}), transport=source_transport(**transport))
    return ValidationContext(http=http, demo_user="alex", threshold_hours=24, high_priority_days=14,
                             now=demo_now(), today=date(2026, 10, 12))  # fmt: skip


def failed(result: Any) -> list[str]:
    return [r.id for r in result.rules if not r.passed]


# --- schema (FR-06) -------------------------------------------------------------------------------


def test_f12_fr06_a_good_ticket_parses() -> None:
    assert ticket().recipient_role == "qa_release" and len(ticket().evidence) == 3


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"title": "x" * 91}, "title"),
        ({"summary": "x" * 601}, "summary"),
        ({"evidence": evidence()[:1]}, "evidence"),
        ({"evidence": evidence()[1:]}, "LIMS approval"),
        (
            {
                "evidence": [
                    evidence()[0],
                    EvidenceItem(system="LIMS", ref="S-0000404", field="status", value="approved"),
                ]
            },
            "ERP",
        ),
        ({"recommended_action": "do_something"}, "recommended_action"),
        ({"priority": "urgent"}, "priority"),
        ({"recipient_role": "planner"}, "recipient_role"),
    ],
)
def test_f12_fr06_schema_limits_and_required_evidence(change: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        ticket(**change)


# --- V1 .. V6 on a good ticket ----------------------------------------------------------------------


def test_f12_fr07_a_good_ticket_passes_every_rule_and_every_evidence_item_is_verified() -> None:
    result = validate_ticket(ticket(), context())
    assert result.passed and result.headline is None
    assert [r.id for r in result.rules] == ["V1", "V2", "V3", "V4", "V5", "V6"]
    assert all(r.message for r in result.rules)
    assert [e.verified for e in result.evidence] == [True, True, True]


def test_f12_fr07_v1_fails_when_the_air_gap_has_resolved() -> None:
    """F12-AC-04 (rule level): the row is no longer an air gap, so V1 fails with 'Air gap resolved'."""
    result = validate_ticket(ticket(), context(row=row_body(air_gap=False, air_gap_hours=0, ud_code="A")))
    assert "V1" in failed(result) and result.headline == "Air gap resolved"


def test_f12_fr07_v1_fails_when_the_row_is_gone() -> None:
    result = validate_ticket(ticket(row_key="RM10067|B5003|99999999"), context())
    assert failed(result)[0] == "V1" and "no longer exists" in (result.headline or "")


# --- AC-03 ------------------------------------------------------------------------------------------


def test_f12_ac03_a_wrong_evidence_value_fails_v2() -> None:
    wrong = evidence()
    wrong[0] = EvidenceItem(system="LIMS", ref="S-0000404", field="approved_at", value="2026-10-10T01:00:00Z")
    result = validate_ticket(ticket(evidence=wrong), context())
    assert failed(result) == ["V2"]
    assert [e.verified for e in result.evidence] == [False, True, True]
    assert (
        "approved_at" in result.evidence[0].message and "2026-10-11T01:00:00Z" in result.evidence[0].message
    )


def test_f12_ac03_hours_off_by_three_fail_v3_but_one_is_tolerated() -> None:
    assert failed(validate_ticket(ticket(hours_in_gap=33), context())) == ["V3"]
    assert failed(validate_ticket(ticket(hours_in_gap=27), context())) == ["V3"]
    assert validate_ticket(ticket(hours_in_gap=31), context()).passed
    assert validate_ticket(ticket(hours_in_gap=29), context()).passed


def test_f12_ac03_the_wrong_recommended_action_with_an_open_deviation_fails_v4() -> None:
    result = validate_ticket(ticket(), context(deviations=[OPEN_DEVIATION]))
    assert failed(result) == ["V4"]
    right = ticket(
        recommended_action="investigate_deviation_first",
        open_deviations=["DEV-000039"],
        evidence=[*evidence(), EvidenceItem(system="QMS", ref="DEV-000039", field="status", value="open")],
        summary="LIMS approved S-0000404 for B5003; deviation DEV-000039 is open. Investigate it first.",
    )
    assert validate_ticket(right, context(deviations=[OPEN_DEVIATION])).passed


def test_f12_fr07_v4_the_open_deviation_list_must_match_qms() -> None:
    result = validate_ticket(ticket(open_deviations=["DEV-000039"]), context())
    assert failed(result) == ["V4"] and "DEV-000039" in result.rules[3].message


def test_f12_fr07_a_closed_deviation_is_not_open() -> None:
    closed = {**OPEN_DEVIATION, "status": "closed", "closed_on": "2026-09-20"}
    assert validate_ticket(ticket(), context(deviations=[closed])).passed


def test_f12_ac03_an_unknown_batch_id_in_the_summary_fails_v6() -> None:
    result = validate_ticket(ticket(summary="Batch B5003 and also batch B9999 are affected."), context())
    assert failed(result) == ["V6"] and "B9999" in result.rules[5].message


@pytest.mark.parametrize(
    "text",
    [
        "Material RM99999 is affected.",
        "Sample S-0009999 was approved.",
        "Lot 19999999 has no decision.",
        "See DEV-009999 for details.",
    ],
)
def test_f12_fr07_v6_every_identifier_kind_must_be_known(text: str) -> None:
    assert failed(validate_ticket(ticket(summary=text), context())) == ["V6"]


def test_f12_fr07_v6_identifiers_from_the_row_and_the_evidence_are_fine() -> None:
    text = "Batch B5003, material RM10067, sample S-0000404, lot 10000459."
    assert validate_ticket(ticket(summary=text, title="B5003 gap"), context()).passed


# --- V5 ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("need_by", "late", "expected"),
    [
        ("2026-10-22", False, "high"),  # 10 days
        ("2026-10-26", False, "high"),  # exactly 14 days
        ("2026-10-27", False, "normal"),  # 15 days
        ("2026-12-01", True, "high"),  # late wins
        ("2026-10-01", False, "high"),  # already past
        (None, False, "normal"),
    ],
)
def test_f12_fr07_v5_priority_follows_the_profile_window(
    need_by: str | None, late: bool, expected: str
) -> None:
    row = row_body(operative_need_by=need_by, late=late)
    other = "normal" if expected == "high" else "high"
    assert validate_ticket(ticket(priority=expected), context(row=row)).passed
    assert failed(validate_ticket(ticket(priority=other), context(row=row))) == ["V5"]


def test_f12_oq140_v5_uses_the_window_it_is_given_not_a_constant() -> None:
    narrow = context()
    narrow.high_priority_days = 5  # 10 days away is now outside the window
    assert failed(validate_ticket(ticket(priority="high"), narrow)) == ["V5"]


# --- payload entry point and unavailable sources ----------------------------------------------------


def test_f12_oq145_a_payload_that_does_not_match_the_schema_fails_as_v0() -> None:
    result = validate_payload({"row_key": ROW_KEY, "title": "x"}, context())
    assert not result.passed and result.rules[0].id == "V0" and not result.rules[0].passed
    assert "summary" in result.rules[0].message
    assert all(not r.passed and "not run" in r.message for r in result.rules[1:])


def test_f12_fr07_a_source_that_cannot_be_read_fails_the_rule_instead_of_crashing() -> None:
    result = validate_ticket(
        ticket(
            evidence=[*evidence(), EvidenceItem(system="QMS", ref="DEV-404404", field="status", value="open")]
        ),
        context(),
    )
    assert "V2" in failed(result) and not result.evidence[-1].verified
    assert "no record" in result.evidence[-1].message


def test_f12_oq140_evidence_must_belong_to_the_batch_of_the_row() -> None:
    """A ticket cannot cite a real record that belongs to another batch."""
    result = validate_ticket(ticket(), context(row=row_body(batch_no="B5004")))
    assert "V2" in failed(result) and not any(e.verified for e in result.evidence)
    assert "another batch" in result.evidence[0].message


def test_f12_oq140_unknown_evidence_fields_are_refused() -> None:
    bad = [*evidence(), EvidenceItem(system="LIMS", ref="S-0000404", field="colour", value="blue")]
    result = validate_ticket(ticket(evidence=bad), context())
    assert failed(result) == ["V2"] and "unknown evidence field" in result.evidence[-1].message


# --- V6 patterns against generated data -------------------------------------------------------------


def test_f12_oq140_the_identifier_patterns_match_every_generated_id(plan: Any) -> None:
    assert plan.batches
    for batch in plan.batches:
        assert BATCH_PATTERN.fullmatch(batch.charg), batch.charg
        assert MATERIAL_PATTERN.fullmatch(batch.matnr), batch.matnr
    # sample, lot and deviation numbers are allocated by the simulators with these formats
    assert SAMPLE_PATTERN.fullmatch(f"S-{404:07d}") and LOT_PATTERN.fullmatch(f"1{459:07d}")
    assert DEVIATION_PATTERN.fullmatch(f"DEV-{39:06d}")
    assert not re.search(LOT_PATTERN, "49" + "00000422")  # goods-movement numbers are not lots


def test_f12_oq140_v3_uses_the_shared_air_gap_function() -> None:
    """V3 reuses r2r_core.airgap, the function the pipeline's flag uses, not a second implementation."""
    import agents.air_gap.validator as validator
    import r2r_core.airgap as shared

    assert validator.air_gap is shared.air_gap
