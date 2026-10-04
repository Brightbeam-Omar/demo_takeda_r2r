"""T5 [TDD]: the single definition of the stage rules (03-domain-model section 4, F06-FR-04)."""

import pytest
from r2r_core.profile import SiteProfile, load_profile
from r2r_core.stage_rules import RULES, StageRule, check_rules


@pytest.fixture(scope="module")
def profile() -> SiteProfile:
    return load_profile("site_a")


def test_f06_fr04_rules_are_in_the_priority_order_of_the_domain_model() -> None:
    assert [(r.id, r.stage_key) for r in RULES] == [
        ("R-REL", "released"),
        ("R-QAR", "qa_release"),
        ("R-QCT", "qc_testing"),
        ("R-QCS", "qc_ship"),
        ("R-RCP", "receipt"),
        ("R-CLO", "call_off"),
        ("R-SMP", "sampling"),
        ("R-PND", "pending"),
    ]


def test_f06_fr04_every_rule_names_a_condition_and_a_description() -> None:
    for rule in RULES:
        assert isinstance(rule, StageRule)
        assert rule.condition_sql.strip() and rule.description.strip()
    assert RULES[-1].condition_sql == "TRUE"  # the last rule catches everything


def test_f06_fr04_rules_agree_with_the_profile(profile: SiteProfile) -> None:
    check_rules(profile)  # no error


def test_f06_fr04_a_profile_missing_a_rule_stage_is_rejected(profile: SiteProfile) -> None:
    stages = [s for s in profile.stages if s.key != "qc_ship"]
    broken = profile.model_copy(update={"stages": stages})
    with pytest.raises(ValueError, match="qc_ship"):
        check_rules(broken)
