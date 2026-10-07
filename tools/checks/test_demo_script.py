"""F14-AC-09: the presenter script has five headings per act and names only real scenario steps.

It also names no company or system beyond the profile terms the UI shows."""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (ROOT / "docs/demo-script.md").read_text()
HEADINGS = ["Clicks", "Say", "Why it matters to the customer", "Time", "If it goes wrong"]
# Acts of the 40-minute version (act 4 is Tier 2). Each is a `## Act N` section.
ACTS = ["1", "2", "3", "5", "6"]
# Tools and companies the script must not name. The profile terms (SAP, LIMS, QMS, QCL) are shown by the UI.
NOT_NAMED = [
    "databricks", "dagster", "postgres", "docker desktop", "playwright", "anthropic", "claude", "openai",
    "snowflake", "oracle", "microsoft", "excel", "azure", "aws",
]  # fmt: skip


def _sections() -> dict[str, str]:
    parts = re.split(r"^## (Act \d+)", SCRIPT, flags=re.M)
    return {parts[i]: parts[i + 1] for i in range(1, len(parts), 2)}


def test_f14_fr03_every_act_has_the_five_headings() -> None:
    sections = _sections()
    assert sorted(sections) == sorted(f"Act {n}" for n in ACTS)
    for name, body in sections.items():
        for heading in HEADINGS:
            assert re.search(rf"^\*\*{re.escape(heading)}", body, flags=re.M), f"{name} has no '{heading}'"


def test_f14_fr03_both_versions_are_there_and_the_short_cut_is_marked_draft() -> None:
    assert "# The 40-minute working call" in SCRIPT
    assert "# The 12-minute leadership cut" in SCRIPT
    assert "**Draft: SME to confirm.**" in SCRIPT


STEP_ID = re.compile(
    r"`((?:lims-approve|ud-post|interface-sync|open-deviation|close-deviation|advance-day|run-pipeline"
    r"|airgap-agent|pull-forward)[A-Za-z0-9-]*)`"
)


def test_f14_fr03_every_step_it_names_exists() -> None:
    scenario = yaml.safe_load((ROOT / "services/sources/scenario/scenarios/site_a.yaml").read_text())
    steps = {step["id"] for step in scenario["steps"]}
    named = set(STEP_ID.findall(SCRIPT))
    assert named and named <= steps, named - steps
    assert {"lims-approve-B1042", "pull-forward-B2077", "airgap-agent", "run-pipeline"} <= named


def test_f14_fr03_it_names_no_company_or_system_beyond_the_profile_terms() -> None:
    lowered = SCRIPT.lower()
    assert [word for word in NOT_NAMED if re.search(rf"\b{re.escape(word)}\b", lowered)] == []


def test_f14_review_it_has_the_tailoring_section_the_close_and_the_extra_questions() -> None:
    assert "# Tailor it to the room" in SCRIPT
    for topic in ["Release speed", "Tacit knowledge", "ERP upgrade", "four to six months", "capitalise"]:
        assert topic.lower() in SCRIPT.lower(), topic
    assert "one site" in SCRIPT and "one or two use cases" in SCRIPT
    for question in ["How do you know the AI is accurate?", "What does it cost to run?", "Is this GxP?"]:
        assert question in SCRIPT, question


def test_f14_fr03_it_names_people_only_by_role() -> None:
    assert "Presenter" in SCRIPT and "SME" in SCRIPT
