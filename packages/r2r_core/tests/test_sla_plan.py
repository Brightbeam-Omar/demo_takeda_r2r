"""T5: plan(): forward, backward, compression, A <= 0, adjusted dates, RAG, auto reason.

F03-AC-01 to AC-05 and AC-07 to AC-09, plus the OQ-020 edge cases. Today is 2026-10-12 and the profile is
site_a unless stated otherwise. Expected dates come from 03-domain-model section 5.2.
"""

from collections.abc import Callable
from datetime import date
from decimal import Decimal

import pytest
from r2r_core.domain import LotType, Rag, RowFacts, StageKey
from r2r_core.profile import SiteProfile
from r2r_core.sla import AdjustedNeedBy, PlanResult, operative_need_by, plan

FactsFactory = Callable[..., RowFacts]
TODAY = date(2026, 10, 12)


def d(text: str) -> date:
    return date.fromisoformat(text)


def sk(*keys: str) -> list[StageKey]:
    return [StageKey(k) for k in keys]


def run(
    profile: SiteProfile,
    facts: FactsFactory,
    adjusted: AdjustedNeedBy | None = None,
    today: date = TODAY,
    **row: object,
) -> PlanResult:
    return plan(facts(**row), profile, today, adjusted)


# --- operative need-by -------------------------------------------------------------------------


def test_f03_ac07_operative_need_by_prefers_the_adjusted_date(facts: FactsFactory) -> None:
    row = facts(system_need_by_locked=d("2026-11-05"))
    assert operative_need_by(row, AdjustedNeedBy(d("2026-12-31"), "CAMPAIGN_PUSHED_OUT")) == d("2026-12-31")
    assert operative_need_by(row, None) == d("2026-11-05")
    assert operative_need_by(facts(), None) is None


# --- forward (no need-by) ----------------------------------------------------------------------


def test_f03_ac01_forward_without_need_by(profile: SiteProfile, facts: FactsFactory) -> None:
    """F03-AC-01: onsite row at sampling, entry 2026-10-08: expected 2026-10-15, 3 days left, green."""
    result = run(profile, facts, current_stage_entry_date=d("2026-10-08"))
    assert result.expected_completion == d("2026-10-15")
    assert result.days_remaining == 3
    assert result.rag == Rag.GREEN
    assert result.late is False
    assert result.compressed is False
    assert result.compression_ratio is None
    assert result.days_in_stage == 4
    assert result.late_reason_auto is None
    # Later stages chain forward (OQ-020 b).
    assert result.must_complete_by == {
        StageKey("sampling"): d("2026-10-15"),
        StageKey("qc_testing"): d("2026-11-26"),
        StageKey("qa_release"): d("2026-12-03"),
    }
    assert result.effective_slas == {
        StageKey("sampling"): 7,
        StageKey("qc_testing"): 42,
        StageKey("qa_release"): 7,
    }


# --- backward, ample budget --------------------------------------------------------------------


def test_f03_ac02_backward_with_ample_budget(profile: SiteProfile, facts: FactsFactory) -> None:
    """F03-AC-02: B = 56, A = 122, no compression; expected 2026-12-13."""
    result = run(
        profile,
        facts,
        current_stage_entry_date=d("2026-10-01"),
        system_need_by_locked=d("2027-01-31"),
    )
    assert result.must_complete_by == {
        StageKey("sampling"): d("2026-12-13"),
        StageKey("qc_testing"): d("2027-01-24"),
        StageKey("qa_release"): d("2027-01-31"),
    }
    assert result.expected_completion == d("2026-12-13")
    assert result.compressed is False
    assert result.compression_ratio is None
    assert result.days_remaining == 62
    assert result.rag == Rag.GREEN


def test_f03_ac02_full_chain_for_a_3pl_offsite_row(profile: SiteProfile, facts: FactsFactory) -> None:
    result = run(
        profile,
        facts,
        stage_key=StageKey("receipt"),
        received_location_type="3pl",
        offsite=True,
        current_stage_entry_date=d("2026-10-01"),
        system_need_by_locked=d("2027-03-01"),
    )
    assert result.must_complete_by == {
        StageKey("receipt"): d("2026-12-20"),
        StageKey("call_off"): d("2026-12-25"),
        StageKey("sampling"): d("2027-01-01"),
        StageKey("qc_ship"): d("2027-01-11"),
        StageKey("qc_testing"): d("2027-02-22"),
        StageKey("qa_release"): d("2027-03-01"),
    }
    assert result.expected_completion == d("2026-12-20")


def test_f03_ac02_available_equal_to_budget_is_not_compressed(
    profile: SiteProfile, facts: FactsFactory
) -> None:
    result = run(
        profile, facts, current_stage_entry_date=d("2026-10-08"), system_need_by_locked=d("2026-12-03")
    )
    assert result.compressed is False  # A = 56 = B
    assert result.expected_completion == d("2026-10-15")


# --- compression -------------------------------------------------------------------------------


def test_f03_ac03_proportional_compression(profile: SiteProfile, facts: FactsFactory) -> None:
    """F03-AC-03: B = 49, A = 35, ratio 5/7: qc 30, qa 5; expected 2026-10-31."""
    result = run(
        profile,
        facts,
        stage_key=StageKey("qc_testing"),
        current_stage_entry_date=d("2026-10-01"),
        system_need_by_locked=d("2026-11-05"),
    )
    assert result.compressed is True
    assert result.compression_ratio == Decimal(35) / Decimal(49)
    assert result.effective_slas == {StageKey("qc_testing"): 30, StageKey("qa_release"): 5}
    assert result.must_complete_by == {
        StageKey("qc_testing"): d("2026-10-31"),
        StageKey("qa_release"): d("2026-11-05"),
    }
    assert result.expected_completion == d("2026-10-31")
    assert result.days_remaining == 19
    assert result.rag == Rag.GREEN


def test_f03_ac03_rounding_is_half_up_not_bankers(profile: SiteProfile, facts: FactsFactory) -> None:
    """sampling 7 x 20/56 = 2.5 rounds to 3 (banker's rounding would give 2); qc is exactly 15."""
    result = run(
        profile, facts, current_stage_entry_date=d("2026-10-08"), system_need_by_locked=d("2026-10-28")
    )
    assert result.effective_slas == {
        StageKey("sampling"): 3,
        StageKey("qc_testing"): 15,
        StageKey("qa_release"): 3,
    }
    assert result.expected_completion == d("2026-10-10")


def test_f03_ac03_half_ratio_rounds_halves_up(profile: SiteProfile, facts: FactsFactory) -> None:
    """Ratio exactly 0.5 (A = 28, B = 56): 3.5 becomes 4, 21 stays 21, 3.5 becomes 4."""
    result = run(
        profile, facts, current_stage_entry_date=d("2026-10-08"), system_need_by_locked=d("2026-11-05")
    )
    assert result.compression_ratio == Decimal("0.5")
    assert list(result.effective_slas.values()) == [4, 21, 4]
    assert result.expected_completion == d("2026-10-11")


def test_f03_ac03_just_under_budget_compresses(profile: SiteProfile, facts: FactsFactory) -> None:
    result = run(
        profile, facts, current_stage_entry_date=d("2026-10-08"), system_need_by_locked=d("2026-12-02")
    )
    assert result.compressed is True  # A = 55 < B = 56
    assert list(result.effective_slas.values()) == [7, 41, 7]
    assert result.expected_completion == d("2026-10-15")


def test_f03_oq020_rounding_floor_can_put_expected_completion_before_the_entry_date(
    profile: SiteProfile, facts: FactsFactory
) -> None:
    """OQ-020 (c): with A = 1 every stage is floored at 1 day, which sums to more than A.

    expected_completion lands before the stage entry date; late and RAG follow from the computed dates.
    """
    entry = d("2026-10-08")
    result = run(profile, facts, current_stage_entry_date=entry, system_need_by_locked=d("2026-10-09"))
    assert list(result.effective_slas.values()) == [1, 1, 1]
    assert result.expected_completion == d("2026-10-07")
    assert result.expected_completion < entry
    assert (result.days_remaining, result.rag, result.late) == (-5, Rag.RED, True)


# --- available time <= 0 -----------------------------------------------------------------------


def test_f03_ac04_need_by_before_entry_is_late(profile: SiteProfile, facts: FactsFactory) -> None:
    """F03-AC-04: need-by 2026-09-30, entry 2026-10-01, stage qa_release: late, red, expected 2026-09-30."""
    result = run(
        profile,
        facts,
        stage_key=StageKey("qa_release"),
        current_stage_entry_date=d("2026-10-01"),
        system_need_by_locked=d("2026-09-30"),
    )
    assert result.expected_completion == d("2026-09-30")
    assert result.late is True
    assert result.rag == Rag.RED
    assert result.days_remaining == -12
    assert result.compressed is True
    assert result.compression_ratio is None


def test_f03_ac04_zero_available_days_compresses_later_stages_to_one_day(
    profile: SiteProfile, facts: FactsFactory
) -> None:
    result = run(
        profile, facts, current_stage_entry_date=d("2026-10-08"), system_need_by_locked=d("2026-10-08")
    )
    assert list(result.effective_slas.values()) == [1, 1, 1]
    assert result.expected_completion == d("2026-10-06")  # N minus the two later stages at one day each


# --- re-evaluation lots ------------------------------------------------------------------------


def test_f03_ac05_reeval_lot_uses_override_slas(profile: SiteProfile, facts: FactsFactory) -> None:
    """F03-AC-05: lot_type 09 at qc_testing, no need-by, entry 2026-10-01: SLA 27, expected 2026-10-28."""
    result = run(
        profile,
        facts,
        stage_key=StageKey("qc_testing"),
        lot_type=LotType.REEVAL,
        current_stage_entry_date=d("2026-10-01"),
    )
    assert result.expected_completion == d("2026-10-28")
    assert result.must_complete_by[StageKey("qa_release")] == d("2026-10-31")  # qa override is 3
    assert result.effective_slas == {StageKey("qc_testing"): 27, StageKey("qa_release"): 3}
    assert result.days_remaining == 16


# --- adjusted need-by --------------------------------------------------------------------------


def test_f03_ac07_adjusted_date_replaces_the_locked_date_even_when_later(
    profile: SiteProfile, facts: FactsFactory
) -> None:
    """F03-AC-07: locked 2026-11-05 would compress; the later adjusted date 2026-12-31 replaces it."""
    row = {"current_stage_entry_date": d("2026-10-08"), "system_need_by_locked": d("2026-11-05")}
    locked_only = run(profile, facts, **row)
    pushed = run(profile, facts, AdjustedNeedBy(d("2026-12-31"), "CAMPAIGN_PUSHED_OUT"), **row)
    assert locked_only.compressed is True
    assert locked_only.expected_completion == d("2026-10-11")
    assert pushed.compressed is False
    assert pushed.must_complete_by[StageKey("qa_release")] == d("2026-12-31")
    assert pushed.expected_completion == d("2026-11-12")


def test_f03_ac07_adjusted_date_works_when_there_is_no_locked_date(
    profile: SiteProfile, facts: FactsFactory
) -> None:
    result = run(
        profile,
        facts,
        AdjustedNeedBy(d("2026-12-31"), "OTHER"),
        current_stage_entry_date=d("2026-10-08"),
    )
    assert result.expected_completion == d("2026-11-12")


# --- automatic late reason ---------------------------------------------------------------------

LATE_ROW = {
    "stage_key": StageKey("qc_testing"),
    "current_stage_entry_date": d("2026-09-01"),
    "system_need_by_locked": d("2026-12-01"),
}


def test_f03_ac08_pulled_forward_and_late_sets_the_automatic_reason(
    profile: SiteProfile, facts: FactsFactory
) -> None:
    """F03-AC-08: adjusted earlier than locked with CAMPAIGN_PULLED_FORWARD, and late."""
    result = run(profile, facts, AdjustedNeedBy(d("2026-10-05"), "CAMPAIGN_PULLED_FORWARD"), **LATE_ROW)
    assert result.expected_completion == d("2026-09-30")
    assert result.late is True
    assert result.late_reason_auto == "CAMPAIGN_PULLED_FORWARD"


@pytest.mark.parametrize("reason", ["EXPEDITE_PRODUCTION", "EXPEDITE_SHIPPING"])
def test_f03_ac08_expedite_reasons_are_reported_as_themselves(
    profile: SiteProfile, facts: FactsFactory, reason: str
) -> None:
    result = run(profile, facts, AdjustedNeedBy(d("2026-10-05"), reason), **LATE_ROW)
    assert result.late_reason_auto == reason


@pytest.mark.parametrize(
    ("adjusted", "locked"),
    [
        (AdjustedNeedBy(d("2026-10-05"), "SUPPLIER_DELAY"), d("2026-12-01")),  # reason does not qualify
        (AdjustedNeedBy(d("2026-10-05"), "CAMPAIGN_PULLED_FORWARD"), d("2026-09-20")),  # later, not earlier
        (AdjustedNeedBy(d("2026-10-05"), "CAMPAIGN_PULLED_FORWARD"), d("2026-10-05")),  # equal, not earlier
        (AdjustedNeedBy(d("2026-10-05"), "CAMPAIGN_PULLED_FORWARD"), None),  # nothing to compare with
    ],
    ids=["other-reason", "later-date", "equal-date", "no-locked-date"],
)
def test_f03_ac08_no_automatic_reason_otherwise(
    profile: SiteProfile, facts: FactsFactory, adjusted: AdjustedNeedBy, locked: date | None
) -> None:
    row = {**LATE_ROW, "system_need_by_locked": locked}
    result = run(profile, facts, adjusted, **row)
    assert result.late is True
    assert result.late_reason_auto is None


def test_f03_ac08_no_automatic_reason_when_not_late(profile: SiteProfile, facts: FactsFactory) -> None:
    result = run(
        profile,
        facts,
        AdjustedNeedBy(d("2026-12-31"), "CAMPAIGN_PULLED_FORWARD"),
        current_stage_entry_date=d("2026-10-08"),
        system_need_by_locked=d("2027-01-31"),
    )
    assert result.expected_completion == d("2026-11-12")
    assert result.late is False
    assert result.late_reason_auto is None


# --- RAG boundaries ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("entry", "days_remaining", "rag", "late"),
    [
        ("2026-10-04", -1, Rag.RED, True),
        ("2026-10-05", 0, Rag.AMBER, False),
        ("2026-10-06", 1, Rag.AMBER, False),
        ("2026-10-07", 2, Rag.AMBER, False),
        ("2026-10-08", 3, Rag.GREEN, False),
    ],
)
def test_f03_ac09_rag_boundaries(
    profile: SiteProfile, facts: FactsFactory, entry: str, days_remaining: int, rag: Rag, late: bool
) -> None:
    """F03-AC-09: -1 red, 0 amber, 2 amber, 3 green (sampling SLA 7, today 2026-10-12)."""
    result = run(profile, facts, current_stage_entry_date=d(entry))
    assert (result.days_remaining, result.rag, result.late) == (days_remaining, rag, late)


# --- rows with nothing to plan -----------------------------------------------------------------


def test_f03_oq020_pending_row_has_no_plan(profile: SiteProfile, facts: FactsFactory) -> None:
    result = run(profile, facts, stage_key=StageKey("pending"), current_stage_entry_date=None)
    assert result.expected_completion is None
    assert result.days_remaining is None
    assert result.rag is None
    assert result.late is False
    assert result.days_in_stage is None
    assert result.must_complete_by == {}
    assert result.effective_slas == {}
    assert result.compressed is False


def test_f03_oq020_released_row_has_no_expected_completion(profile: SiteProfile, facts: FactsFactory) -> None:
    result = run(
        profile,
        facts,
        stage_key=StageKey("released"),
        current_stage_entry_date=d("2026-10-01"),
        system_need_by_locked=d("2026-11-01"),
    )
    assert (result.expected_completion, result.rag, result.late) == (None, None, False)
    assert result.days_in_stage == 11


def test_f03_oq020_started_stage_without_an_entry_date_has_no_plan(
    profile: SiteProfile, facts: FactsFactory
) -> None:
    result = run(profile, facts, current_stage_entry_date=None)
    assert result.expected_completion is None
    assert result.days_in_stage is None


def test_f03_oq020_stage_not_applicable_to_the_row_is_an_error(
    profile: SiteProfile, facts: FactsFactory
) -> None:
    with pytest.raises(ValueError, match="call_off"):
        run(profile, facts, stage_key=StageKey("call_off"), received_location_type="onsite")


def test_f03_oq020_unknown_stage_is_an_error(profile: SiteProfile, facts: FactsFactory) -> None:
    with pytest.raises(KeyError):
        run(profile, facts, stage_key=StageKey("nowhere"))


# --- story batch B2077 (act 5 of the demo) -----------------------------------------------------


def test_f03_story_b2077_pull_forward(profile: SiteProfile, facts: FactsFactory) -> None:
    """Golden test for the act-5 moment: a planner pulls the campaign forward and the row compresses.

    Onsite, at sampling since 2026-10-08, locked need-by 2026-12-03, today 2026-10-12.
    """
    row = {
        "row_key": "RM10031|B2077|10002077",
        "current_stage_entry_date": d("2026-10-08"),
        "system_need_by_locked": d("2026-12-03"),
    }

    before = run(profile, facts, **row)
    assert before.compressed is False
    assert before.expected_completion == d("2026-10-15")
    assert (before.days_remaining, before.rag, before.late) == (3, Rag.GREEN, False)

    pulled = run(profile, facts, AdjustedNeedBy(d("2026-11-26"), "CAMPAIGN_PULLED_FORWARD"), **row)
    assert pulled.compressed is True
    assert pulled.compression_ratio == Decimal(49) / Decimal(56)
    assert list(pulled.effective_slas.values()) == [6, 37, 6]
    assert pulled.expected_completion == d("2026-10-14")
    assert (pulled.days_remaining, pulled.rag, pulled.late) == (2, Rag.AMBER, False)
    assert pulled.late_reason_auto is None  # not late, so the pull-forward is not offered as an excuse
