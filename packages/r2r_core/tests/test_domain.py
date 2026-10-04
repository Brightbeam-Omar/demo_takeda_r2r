"""T3: domain enums and RowFacts [F03-FR-04]."""

import dataclasses
from datetime import date

import pytest
from r2r_core.applies_if import ALIASES, BOOLEAN_FIELDS, STRING_FIELDS, parse_applies_if
from r2r_core.domain import LotType, OverrideField, Rag, Role, RowFacts, StageKey, stage_keys
from r2r_core.profile import load_profile


def make_facts(**overrides: object) -> RowFacts:
    base: dict[str, object] = {
        "row_key": "RM10001|B1|10000001",
        "stage_key": StageKey("sampling"),
        "lot_type": LotType.INITIAL,
        "received_location_type": "onsite",
        "offsite": False,
        "current_stage_entry_date": date(2026, 10, 8),
        "system_need_by_locked": None,
        "on_hold": False,
        "ud_rejected": False,
        "lims_status": "none",
        "ud_effective": False,
        "ud_code": None,
        "lims_approved_at": None,
    }
    return RowFacts(**{**base, **overrides})


def test_f03_fr04_stage_keys_follow_the_profile_order() -> None:
    keys = stage_keys(load_profile("site_a"))
    assert keys[0] == "pending"
    assert keys[-1] == "released"
    assert len(keys) == 8


def test_f03_fr04_enum_values_match_the_contracts() -> None:
    assert [m.value for m in LotType] == ["01", "09"]
    assert [m.value for m in Rag] == ["green", "amber", "red"]
    assert [m.value for m in Role] == ["planner", "qc_lead", "qa_release", "viewer", "admin"]
    assert [m.value for m in OverrideField] == [
        "adjusted_need_by_date", "expedite", "manual_status", "delivery_date", "delivery_location",
    ]  # fmt: skip


def test_f03_fr04_enums_compare_equal_to_plain_strings() -> None:
    assert LotType("09") == "09"
    assert Rag.RED == "red"


def test_f03_fr04_row_facts_is_frozen() -> None:
    facts = make_facts()
    with pytest.raises(dataclasses.FrozenInstanceError):
        facts.offsite = True


def test_f03_oq017_applies_if_fields_exist_on_row_facts() -> None:
    names = {f.name for f in dataclasses.fields(RowFacts)}
    assert names >= (STRING_FIELDS | BOOLEAN_FIELDS)
    assert set(ALIASES.values()) <= names


def test_f03_oq017_site_a_conditions_evaluate_against_row_facts() -> None:
    profile = load_profile("site_a")
    call_off = parse_applies_if(profile.stage("call_off").applies_if or "")
    qc_ship = parse_applies_if(profile.stage("qc_ship").applies_if or "")
    assert call_off.evaluate(make_facts(received_location_type="3pl")) is True
    assert call_off.evaluate(make_facts()) is False
    assert qc_ship.evaluate(make_facts(offsite=True)) is True
    assert qc_ship.evaluate(make_facts()) is False
