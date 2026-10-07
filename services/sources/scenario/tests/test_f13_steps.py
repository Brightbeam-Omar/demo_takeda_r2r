"""T1: the step schema, the YAML loader, the template filler and the precondition checks [F13-FR-01, FR-02]."""

from pathlib import Path

import pytest
from fakes import World
from scenario.lookups import check_precondition, resolve_var
from scenario.steps import Precondition, StepError, fill, load_steps, parse_steps

TIER_1 = {
    "lims-approve-B1042", "ud-post-B5003", "interface-sync-B5003", "open-deviation-B1042",
    "close-deviation-B3150", "advance-day", "run-pipeline", "airgap-agent", "pull-forward-B2077",
}  # fmt: skip


def test_f13_fr02_the_shipped_scenario_has_every_tier_1_step() -> None:
    steps = load_steps()
    assert {step.id for step in steps} == TIER_1
    for step in steps:
        assert step.title and step.talk_track and step.actions


def test_f13_fr02_the_two_b5003_steps_are_alternatives() -> None:
    by_id = {step.id: step for step in load_steps()}
    for step_id in ("ud-post-B5003", "interface-sync-B5003"):
        (check,) = by_id[step_id].preconditions
        assert (check.kind, check.batch, check.equals) == ("air_gap", "B5003", True)


def test_f13_fr01_actions_are_declared_in_order() -> None:
    kinds = [action.kind for action in {s.id: s for s in load_steps()}["lims-approve-B1042"].actions]
    assert kinds == ["event", "run_pipeline", "wait_sync"]


@pytest.mark.parametrize(
    ("step", "message"),
    [
        ({"id": "a", "title": "t", "talk_track": "x", "actions": [{"do": "teleport"}]}, "unknown action"),
        ({"id": "a", "title": "t", "talk_track": "x", "actions": [{"do": "event", "path": "/p"}]}, "service"),
        ({"id": "a", "title": "t", "talk_track": "x", "actions": [{"do": "clock_advance"}]}, "exactly one"),
        ({"id": "a", "title": "t", "actions": [{"do": "run_pipeline"}]}, "missing talk_track"),
        ({"title": "t", "talk_track": "x", "actions": [{"do": "run_pipeline"}]}, "needs an id"),
        (
            {"id": "a", "title": "t", "talk_track": "x", "actions": [{"do": "run_pipeline"}],
             "preconditions": [{"kind": "mood", "batch": "B1", "equals": 1, "message": "m"}]},
            "unknown precondition",
        ),
    ],
)  # fmt: skip
def test_f13_fr01_a_bad_step_is_refused_with_a_reason(step: dict[str, object], message: str) -> None:
    with pytest.raises(StepError, match=message):
        parse_steps({"steps": [step]})


def test_f13_fr01_duplicate_ids_are_refused() -> None:
    step = {"id": "a", "title": "t", "talk_track": "x", "actions": [{"do": "run_pipeline"}]}
    with pytest.raises(StepError, match="duplicate"):
        parse_steps({"steps": [step, step]})


def test_f13_fr01_loads_from_a_file(tmp_path: Path) -> None:
    path = tmp_path / "s.yaml"
    path.write_text("steps:\n  - {id: a, title: T, talk_track: X, actions: [{do: run_pipeline}]}\n")
    assert [s.id for s in load_steps(path)] == ["a"]


def test_f13_fr01_fill_replaces_names_and_dotted_fields_in_nested_values() -> None:
    variables = {"row": {"row_key": "A|B|1"}, "n": 5}
    filled = fill({"path": "/rows/${row.row_key}", "body": [{"x": "${n}"}], "keep": 3}, variables)
    assert filled == {"path": "/rows/A|B|1", "body": [{"x": "5"}], "keep": 3}


def test_f13_fr01_fill_refuses_an_unknown_name() -> None:
    with pytest.raises(StepError, match=r"unknown variable \$\{row.nope\}"):
        fill("${row.nope}", {"row": {}})


def test_f13_fr01_a_precondition_holds_or_returns_its_message() -> None:
    world = World()
    gateway = world.gateway()
    holds = Precondition("stage", "B1042", "qc_testing", "not in QC")
    assert check_precondition(gateway, holds) is None
    world.rows["B1042"]["stage_key"] = "qa_release"
    assert check_precondition(gateway, holds) == "not in QC"


def test_f13_fr01_preconditions_read_air_gap_deviations_and_need_by() -> None:
    world = World()
    gateway = world.gateway()
    assert check_precondition(gateway, Precondition("air_gap", "B5003", True, "m")) is None
    assert check_precondition(gateway, Precondition("open_deviations", "B3150", 1, "m")) is None
    assert check_precondition(gateway, Precondition("open_deviations", "B1042", 0, "m")) is None
    assert check_precondition(gateway, Precondition("adjusted_need_by", "B2077", False, "m")) is None
    world.rows["B2077"]["adjusted_need_by_date"] = "2026-11-26"
    assert check_precondition(gateway, Precondition("adjusted_need_by", "B2077", False, "m")) == "m"


def test_f13_fr01_variables_are_looked_up_in_the_services() -> None:
    gateway = World().gateway()
    assert resolve_var(gateway, "sample", {"resolve": "sample", "batch": "B1042"})["sample_id"] == "S-1"
    assert resolve_var(gateway, "row", {"resolve": "row", "batch": "B5003"})["inspection_lot_no"] == "100"
    assert resolve_var(gateway, "d", {"resolve": "deviation", "batch": "B3150"})["deviation_no"] == "DEV-1"
    with pytest.raises(StepError, match="no open deviation"):
        resolve_var(gateway, "d", {"resolve": "deviation", "batch": "B1042"})
