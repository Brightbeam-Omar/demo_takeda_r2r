"""T4: applicable stages and per-stage SLAs [F03-FR-05, F03-AC-05, F03-AC-06]."""

import copy
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml
from r2r_core.domain import LotType, RowFacts, StageKey
from r2r_core.profile import SiteProfile, parse_profile
from r2r_core.sla import applicable_stages, sla_for

FactsFactory = Callable[..., RowFacts]
SITE_A = Path(__file__).resolve().parents[3] / "config" / "site-profiles" / "site_a.yaml"


def _keys(stages: list[StageKey]) -> list[str]:
    return [str(s) for s in stages]


def test_f03_ac06_3pl_offsite_row_includes_call_off_and_qc_ship(
    profile: SiteProfile, facts: FactsFactory
) -> None:
    row = facts(received_location_type="3pl", offsite=True)
    assert _keys(applicable_stages(row, profile)) == [
        "receipt", "call_off", "sampling", "qc_ship", "qc_testing", "qa_release",
    ]  # fmt: skip


def test_f03_ac06_onsite_onsite_test_row_excludes_both(profile: SiteProfile, facts: FactsFactory) -> None:
    row = facts(received_location_type="onsite", offsite=False)
    assert _keys(applicable_stages(row, profile)) == ["receipt", "sampling", "qc_testing", "qa_release"]


@pytest.mark.parametrize(
    ("location", "offsite", "expected"),
    [
        ("3pl", False, ["receipt", "call_off", "sampling", "qc_testing", "qa_release"]),
        ("onsite", True, ["receipt", "sampling", "qc_ship", "qc_testing", "qa_release"]),
    ],
)
def test_f03_ac06_each_condition_applies_independently(
    profile: SiteProfile, facts: FactsFactory, location: str, offsite: bool, expected: list[str]
) -> None:
    row = facts(received_location_type=location, offsite=offsite)
    assert _keys(applicable_stages(row, profile)) == expected


def test_f03_ac06_pending_and_released_are_never_applicable(
    profile: SiteProfile, facts: FactsFactory
) -> None:
    keys = _keys(applicable_stages(facts(received_location_type="3pl", offsite=True), profile))
    assert "pending" not in keys
    assert "released" not in keys


def _custom(mutate: Any) -> SiteProfile:
    data: dict[str, Any] = copy.deepcopy(yaml.safe_load(SITE_A.read_text()))
    mutate(data)
    return parse_profile(data)


def test_f03_oq017_applicability_is_read_from_the_profile_not_hard_coded(facts: FactsFactory) -> None:
    """Change the profile's applies_if and the answer changes with it."""

    def mutate(data: dict[str, Any]) -> None:
        data["stages"][2]["applies_if"] = "lot_type == '09'"  # call_off now depends on lot type

    custom = _custom(mutate)
    assert "call_off" not in _keys(applicable_stages(facts(received_location_type="3pl"), custom))
    reeval = facts(received_location_type="onsite", lot_type=LotType.REEVAL)
    assert "call_off" in _keys(applicable_stages(reeval, custom))


def test_f03_oq017_a_stage_with_zero_sla_takes_no_part_in_sla_maths(facts: FactsFactory) -> None:
    def mutate(data: dict[str, Any]) -> None:
        data["stages"][3]["sla_days"] = 0  # sampling

    custom = _custom(mutate)
    assert "sampling" not in _keys(applicable_stages(facts(), custom))


@pytest.mark.parametrize(
    ("stage", "lot_type", "expected"),
    [
        ("receipt", LotType.INITIAL, 10),
        ("call_off", LotType.INITIAL, 5),
        ("sampling", LotType.INITIAL, 7),
        ("qc_ship", LotType.INITIAL, 10),
        ("qc_testing", LotType.INITIAL, 42),
        ("qa_release", LotType.INITIAL, 7),
        ("sampling", LotType.REEVAL, 5),
        ("qc_testing", LotType.REEVAL, 27),
        ("qa_release", LotType.REEVAL, 3),
        ("receipt", LotType.REEVAL, 10),  # no override given: the base SLA applies
        ("qc_ship", LotType.REEVAL, 10),
    ],
)
def test_f03_ac05_sla_for_applies_reeval_overrides(
    profile: SiteProfile, stage: str, lot_type: LotType, expected: int
) -> None:
    assert sla_for(StageKey(stage), lot_type, profile) == expected


def test_f03_ac05_sla_for_an_unknown_stage_raises(profile: SiteProfile) -> None:
    with pytest.raises(KeyError):
        sla_for(StageKey("nowhere"), LotType.INITIAL, profile)
