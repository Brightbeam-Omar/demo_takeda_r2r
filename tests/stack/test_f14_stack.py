"""F14 demo hardening against the real containers (OQ-166 to OQ-173).

The last test is the CI check of the re-recording rule (F14-FR-18): after a reset the recorded answers must cover
the four demo-start air gaps, and it fails (it is never skipped) when they do not. Each test starts from a reset.
"""

from typing import Any

import httpx
import pytest
from test_f13_stack import (
    ADMIN,
    AGENTS,
    ALEX,
    APP_API,
    SCENARIO,
    TOKEN,
    _air_gap_batches,
    _get,
    _maybe_row,
    _reset,
    _row,
    _scalar,
    _step,
    needs_recordings,
)

pytestmark = pytest.mark.stack
PAT = {"X-Demo-User": "pat"}


def _listing() -> dict[str, dict[str, Any]]:
    return {s["id"]: s for s in httpx.get(f"{SCENARIO}/scenario/steps", headers=TOKEN, timeout=60).json()}


def test_f14_ac11_b1042_never_becomes_an_air_gap_however_many_days_pass() -> None:
    """OQ-166: the interface records the LIMS results, so reset, approve, two days: still the same four batches."""
    _reset()
    recorded = _air_gap_batches()
    assert len(recorded) == 4 and "B1042" not in recorded
    _step("lims-approve-B1042")
    assert _row("B1042")["stage_key"] == "qa_release"
    assert _air_gap_batches() == recorded
    _step("advance-day")
    _step("advance-day")
    assert _air_gap_batches() == recorded, "B1042 (or another batch) joined or left the air gaps"


def test_f14_ac13_the_steps_come_in_script_order_and_a_pending_proposal_holds_back_the_b5003_steps() -> None:
    """OQ-168: groups in order; ud-post-B5003 and interface-sync-B5003 wait while the B5003 proposal is pending."""
    _reset()
    steps = list(_listing().values())
    order = ["Act 3", "Act 5", "Act 6", "After act 6", "Extras"]
    assert [s["group"] for s in steps] == sorted((s["group"] for s in steps), key=order.index)
    assert {s["id"]: s["group"] for s in steps}["ud-post-B5003"] == "After act 6"
    assert _listing()["ud-post-B5003"]["preconditions"] == "met"  # no proposal yet


@needs_recordings
def test_f14_ac13_ud_post_waits_for_the_b5003_proposal_to_be_decided() -> None:
    _reset()
    _step("airgap-agent")
    listing = _listing()
    for step in ("ud-post-B5003", "interface-sync-B5003"):
        assert listing[step]["preconditions"] == "unmet"
        assert "waiting for a decision" in listing[step]["messages"][0]
    refused = httpx.post(f"{SCENARIO}/scenario/steps/ud-post-B5003/run", headers=TOKEN, timeout=60)
    assert refused.status_code == 409
    proposals = _get(f"{AGENTS}/proposals", ALEX)["rows"]
    b5003 = next(p for p in proposals if p["batch_no"] == "B5003")
    approved = httpx.post(f"{AGENTS}/proposals/{b5003['id']}/approve", headers=ALEX, timeout=60)
    assert approved.status_code == 200, approved.text
    assert _listing()["ud-post-B5003"]["preconditions"] == "met"


def test_f14_ac14_the_act_5_fallback_is_safe_to_press_twice() -> None:
    """OQ-169: once B2077 is adjusted the step is unmet ('already adjusted'), refused, and writes nothing."""
    _reset()
    _step("pull-forward-B2077")
    assert _row("B2077")["adjusted_need_by_date"] == "2026-11-26"
    listed = _listing()["pull-forward-B2077"]
    assert listed["preconditions"] == "unmet" and "already adjusted" in listed["messages"][0]
    overrides = _scalar("app", "SELECT count(*) FROM override_value")
    audits = _scalar("app", "SELECT count(*) FROM audit_event WHERE action = 'need_by_set'")
    refused = httpx.post(f"{SCENARIO}/scenario/steps/pull-forward-B2077/run", headers=TOKEN, timeout=60)
    assert refused.status_code == 409
    assert _scalar("app", "SELECT count(*) FROM override_value") == overrides
    assert _scalar("app", "SELECT count(*) FROM audit_event WHERE action = 'need_by_set'") == audits
    assert _row("B2077")["adjusted_need_by_date"] == "2026-11-26"  # the act can carry on


def test_f14_ac15_after_a_reset_every_persona_has_the_demo_presets() -> None:
    """OQ-170: the profile's presets come back with the reset, for each persona."""
    _reset()
    for persona in ("pat", "quinn", "alex", "sam", "admin"):
        presets = _get(f"{APP_API}/api/presets", {"X-Demo-User": persona})
        names = {p["name"] for p in presets}
        assert {"Late batches", "Air gaps", "On hold or expedite"} <= names, (persona, names)
    reference = _get(f"{APP_API}/api/reference")["demo"]
    assert reference["hide_placeholders"] is True and reference["default_columns"][:3] == [
        "material",
        "batch",
        "stage",
    ]


def test_f14_ac18_after_a_reset_the_replay_keys_of_the_four_demo_start_air_gaps_exist() -> None:
    """OQ-173: fails when datagen, the contract or the agent tools changed without `make record-agents`."""
    _reset()
    check = _get(f"{AGENTS}/agents/air_gap/replay-check", ADMIN)
    assert check["recording_files"] > 0, "no recordings: run make demo-reset && make record-agents"
    assert check["demo_start"] is True, [c["batch_no"] for c in check["candidates"]]
    missing = [c["batch_no"] for c in check["candidates"] if not c["replays"]]
    assert len(check["candidates"]) == 4 and not missing, (
        f"no replay key for {missing}: run make demo-reset && make record-agents && make doctor EXPECT_UP=1"
    )
    assert _maybe_row("B5003") is not None
