"""T5 [TDD]: the stage engine, rule by rule (F06-FR-04, F06-AC-02, F06-AC-03)."""

from pathlib import Path
from typing import Any

import pytest
from r2r_core.profile import SiteProfile
from stage_rows import D, flat_row, run_engine


def stage_of(profile: SiteProfile, tmp_path: Path, **values: Any) -> dict[str, Any]:
    row = flat_row(**values)
    return run_engine([row], profile, tmp_path)[row["row_key"]]


APPROVED = {
    "lims_status": "approved",
    "sample_collected_date": D(2026, 9, 5),
    "lims_approved_date": D(2026, 10, 6),
}


@pytest.mark.parametrize(
    ("rule", "stage", "values"),
    [
        ("R-REL", "released", {"ud_code": "A", **APPROVED, "ud_date": D(2026, 10, 8)}),
        ("R-REL", "released", {"ud_code": "A4", "ud_date": D(2026, 10, 8)}),
        ("R-QAR", "qa_release", APPROVED),
        ("R-QAR", "qa_release", {**APPROVED, "ud_code": "R", "ud_date": D(2026, 10, 8)}),
        ("R-QCT", "qc_testing", {"lims_status": "in_progress", "sample_collected_date": D(2026, 9, 5)}),
        (
            "R-QCT",
            "qc_testing",
            {
                "lims_status": "in_progress",
                "offsite_test": True,
                "sample_collected_date": D(2026, 9, 5),
                "sample_shipped_date": D(2026, 9, 8),
            },
        ),
        ("R-QCT", "qc_testing", {"lims_status": "rejected", "sample_collected_date": D(2026, 9, 5)}),
        (
            "R-QCS",
            "qc_ship",
            {"lims_status": "in_progress", "offsite_test": True, "sample_collected_date": D(2026, 9, 5)},
        ),
        ("R-RCP", "receipt", {"inbound_check_status": "open", "inbound_check_completed_date": None}),
        ("R-RCP", "receipt", {"inbound_check_status": "failed", "inbound_check_completed_date": None}),
        ("R-CLO", "call_off", {"received_location_type": "3pl"}),
        ("R-SMP", "sampling", {}),
        ("R-SMP", "sampling", {"inbound_check_status": "none", "inbound_check_completed_date": None}),
        (
            "R-PND",
            "pending",
            {"gr_date": None, "inbound_check_status": "open", "inbound_check_completed_date": None},
        ),
    ],
)
def test_f06_ac02_each_rule_fires_on_a_minimal_row(
    profile: SiteProfile, tmp_path: Path, rule: str, stage: str, values: dict[str, Any]
) -> None:
    row = stage_of(profile, tmp_path, **values)
    assert (row["stage_rule_id"], row["stage_key"]) == (rule, stage)


@pytest.mark.parametrize(
    ("winner", "values"),
    [
        # a row that satisfies several rules takes the first by priority
        ("R-REL", {"ud_code": "A", **APPROVED, "inbound_check_status": "open", "received_location_type": "3pl"}),
        ("R-QAR", {**APPROVED, "inbound_check_status": "open", "received_location_type": "3pl"}),  # QAR and RCP/CLO/SMP
        ("R-QCT", {"lims_status": "in_progress", "sample_collected_date": D(2026, 9, 5), "inbound_check_status": "open"}),
        ("R-QCS", {"lims_status": "in_progress", "offsite_test": True, "sample_collected_date": D(2026, 9, 5),
                   "inbound_check_status": "failed", "received_location_type": "3pl"}),  # QCS beats RCP and CLO
        ("R-RCP", {"inbound_check_status": "open", "received_location_type": "3pl"}),  # RCP beats CLO and SMP
        ("R-CLO", {"received_location_type": "3pl"}),  # CLO beats SMP
    ],
)  # fmt: skip
def test_f06_ac02_the_first_matching_rule_wins(
    profile: SiteProfile, tmp_path: Path, winner: str, values: dict[str, Any]
) -> None:
    assert stage_of(profile, tmp_path, **values)["stage_rule_id"] == winner


def test_f06_ac02_a_3pl_row_that_was_called_off_is_in_sampling(profile: SiteProfile, tmp_path: Path) -> None:
    row = stage_of(profile, tmp_path, received_location_type="3pl", transfer_to_site_date=D(2026, 9, 10))
    assert row["stage_key"] == "sampling"


def test_f06_ac02_a_reeval_lot_starts_its_cycle_at_the_lot_start(
    profile: SiteProfile, tmp_path: Path
) -> None:
    row = stage_of(
        profile, tmp_path, lot_type="09", lot_start_date=D(2026, 10, 8), inbound_check_status="none",
        inbound_check_completed_date=None, gr_date=D(2026, 1, 5),
    )  # fmt: skip
    assert (row["stage_key"], row["current_stage_entry_date"]) == ("sampling", D(2026, 10, 8))
    reborn = stage_of(
        profile, tmp_path, lot_type="09", lot_start_date=None, gr_date=None, inbound_check_status="none"
    )
    assert reborn["stage_key"] == "pending"


def test_f06_ac03_a_rejected_ud_waits_in_qa_release_with_ud_rejected(
    profile: SiteProfile, tmp_path: Path
) -> None:
    row = stage_of(profile, tmp_path, **APPROVED, ud_code="R", ud_date=D(2026, 10, 8))
    assert (row["stage_key"], row["ud_rejected"]) == ("qa_release", True)
    accepted = stage_of(profile, tmp_path, **APPROVED, ud_code="A", ud_date=D(2026, 10, 8))
    assert accepted["ud_rejected"] is False


def test_f06_fr04_stage_sort_follows_the_profile_order(profile: SiteProfile, tmp_path: Path) -> None:
    order = {s.key: i for i, s in enumerate(profile.stages, start=1)}
    samples = {
        "pending": {"gr_date": None},
        "receipt": {"inbound_check_status": "open"},
        "sampling": {},
        "qa_release": APPROVED,
        "released": {"ud_code": "A"},
    }
    for stage, values in samples.items():
        row = stage_of(profile, tmp_path, **values)
        assert (row["stage_key"], row["stage_sort"]) == (stage, order[stage])


def test_f06_fr04_onsite_flow_entry_and_exit_dates(profile: SiteProfile, tmp_path: Path) -> None:
    row = stage_of(profile, tmp_path, **APPROVED, ud_code="A", ud_date=D(2026, 10, 8))
    assert (row["receipt_entry"], row["receipt_exit"]) == (D(2026, 9, 1), D(2026, 9, 3))
    assert (row["call_off_entry"], row["call_off_exit"]) == (None, None)  # onsite: no call-off
    assert (row["sampling_entry"], row["sampling_exit"]) == (D(2026, 9, 3), D(2026, 9, 5))
    assert (row["qc_ship_entry"], row["qc_ship_exit"]) == (None, None)  # onsite test: no shipping
    assert (row["qc_testing_entry"], row["qc_testing_exit"]) == (D(2026, 9, 5), D(2026, 10, 6))
    assert (row["qa_release_entry"], row["qa_release_exit"]) == (D(2026, 10, 6), D(2026, 10, 8))
    assert row["current_stage_entry_date"] is None  # released rows have no current stage entry


def test_f06_fr04_3pl_and_offsite_flow_entry_and_exit_dates(profile: SiteProfile, tmp_path: Path) -> None:
    row = stage_of(
        profile, tmp_path, received_location_type="3pl", transfer_to_site_date=D(2026, 9, 10), offsite_test=True,
        sample_collected_date=D(2026, 9, 12), sample_shipped_date=D(2026, 9, 15), lims_status="in_progress",
    )  # fmt: skip
    assert (row["call_off_entry"], row["call_off_exit"]) == (D(2026, 9, 3), D(2026, 9, 10))
    assert (row["sampling_entry"], row["sampling_exit"]) == (D(2026, 9, 10), D(2026, 9, 12))
    assert (row["qc_ship_entry"], row["qc_ship_exit"]) == (D(2026, 9, 12), D(2026, 9, 15))
    assert (row["qc_testing_entry"], row["qc_testing_exit"]) == (D(2026, 9, 15), None)
    assert (row["stage_key"], row["current_stage_entry_date"]) == ("qc_testing", D(2026, 9, 15))


def test_f06_fr04_receipt_exit_falls_back_to_the_entry_when_there_is_no_check(
    profile: SiteProfile, tmp_path: Path
) -> None:
    row = stage_of(profile, tmp_path, inbound_check_status="none", inbound_check_completed_date=None)
    assert (row["receipt_entry"], row["receipt_exit"], row["sampling_entry"]) == (
        D(2026, 9, 1),
        D(2026, 9, 1),
        D(2026, 9, 1),
    )


def test_f06_oq044_a_failed_check_has_no_receipt_exit_so_later_entries_stay_empty(
    profile: SiteProfile, tmp_path: Path
) -> None:
    row = stage_of(profile, tmp_path, inbound_check_status="failed", inbound_check_completed_date=None)
    assert (row["stage_key"], row["receipt_exit"], row["sampling_entry"]) == ("receipt", None, None)
    assert row["current_stage_entry_date"] == D(2026, 9, 1)


def test_f06_fr04_pending_rows_have_no_dates(profile: SiteProfile, tmp_path: Path) -> None:
    row = stage_of(
        profile, tmp_path, gr_date=None, inbound_check_status="open", inbound_check_completed_date=None
    )
    assert row["stage_key"] == "pending"
    assert row["current_stage_entry_date"] is None and row["receipt_entry"] is None


def test_f06_fr04_the_output_columns_are_those_of_the_contract(profile: SiteProfile, tmp_path: Path) -> None:
    row = stage_of(profile, tmp_path)
    assert list(row) == [
        "row_key", "stage_key", "stage_rule_id", "cycle_start_date", "ud_effective", "stage_sort",
        "current_stage_entry_date", "lims_rejected",
        "receipt_entry", "receipt_exit", "call_off_entry", "call_off_exit", "sampling_entry", "sampling_exit",
        "qc_ship_entry", "qc_ship_exit", "qc_testing_entry", "qc_testing_exit", "qa_release_entry",
        "qa_release_exit", "on_hold", "erp_blocked", "re_eval", "offsite", "full_spec", "ud_rejected",
        "deviation_light", "inbound_light",
    ]  # fmt: skip


def test_f06_fr04_a_profile_stage_with_an_sla_but_no_date_rule_is_an_error(profile: SiteProfile) -> None:
    from r2r_core.profile import Stage
    from r2r_pipeline.stage_engine import engine_variables

    extra = Stage(key="quarantine", label="Quarantine", sla_days=3, team="QA", action="Hold")
    broken = profile.model_copy(update={"stages": [*profile.stages, extra]})
    with pytest.raises(ValueError, match="quarantine"):
        engine_variables(broken)
    assert engine_variables(profile)["dated_stages"]  # the real profile is fine


def test_f06_fr09_the_pipeline_steps_do_not_depend_on_dagster() -> None:
    """Checked in a fresh interpreter: other tests (the Dagster job) import dagster into this process."""
    import subprocess
    import sys

    code = (
        "import sys, r2r_pipeline.extract, r2r_pipeline.transform, r2r_pipeline.pipeline;"
        "print([m for m in sys.modules if m == 'dagster' or m.startswith('dagster.')])"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert result.stdout.strip() == "[]"
