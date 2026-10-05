"""T6 [TDD]: applicable_sla_json (F06-FR-05, F06-AC-05, F06-AC-06)."""

import json
from datetime import date
from pathlib import Path

import pytest
from fixture_world import World
from r2r_core.profile import SiteProfile, load_profile
from r2r_pipeline.context import new_context
from r2r_pipeline.lake import read_delta
from r2r_pipeline.transform import transform

D = date


def slas(profile: SiteProfile, tmp_path: Path, world: World) -> dict[str, list[tuple[str, int]]]:
    world.write(tmp_path)
    transform(new_context(profile, tmp_path, snapshot_date=D(2026, 10, 12)))
    table = read_delta(tmp_path, "staging.batch_stage").select(["row_key", "applicable_sla_json"])
    return {
        row["row_key"]: [
            (item["stage_key"], item["sla_days"]) for item in json.loads(row["applicable_sla_json"])
        ]
        for row in table.to_pylist()
    }


def world_with_every_route() -> World:
    world = World()
    world.receive("B1", "10000001", D(2026, 9, 1))  # onsite, onsite test
    world.receive("B2", "10000002", D(2026, 9, 1), lgort="0200")  # received at a 3PL
    world.receive("B3", "10000003", D(2026, 9, 1))
    world.sample("10000003", D(2026, 9, 10), offsite=True, charg="B3")  # offsite test
    world.receive("B4", "10000004", D(2026, 9, 1))
    world.reeval("B4", "10000009", D(2026, 10, 1), matnr="RM1")
    return world


def test_f06_fr05_the_list_follows_the_route_of_each_row(profile: SiteProfile, tmp_path: Path) -> None:
    result = slas(profile, tmp_path, world_with_every_route())
    assert result["RM1|B1|10000001"] == [
        ("receipt", 10),
        ("sampling", 7),
        ("qc_testing", 42),
        ("qa_release", 7),
    ]
    assert result["RM1|B2|10000002"] == [
        ("receipt", 10), ("call_off", 5), ("sampling", 7), ("qc_testing", 42), ("qa_release", 7),
    ]  # fmt: skip
    assert result["RM1|B3|10000003"] == [
        ("receipt", 10), ("sampling", 7), ("qc_ship", 10), ("qc_testing", 42), ("qa_release", 7),
    ]  # fmt: skip


def test_f06_ac05_a_reeval_row_has_the_reeval_slas(profile: SiteProfile, tmp_path: Path) -> None:
    result = slas(profile, tmp_path, world_with_every_route())
    assert result["RM1|B4|10000009"] == [
        ("receipt", 10),
        ("sampling", 5),
        ("qc_testing", 27),
        ("qa_release", 3),
    ]
    assert result["RM1|B4|10000004"] == [
        ("receipt", 10),
        ("sampling", 7),
        ("qc_testing", 42),
        ("qa_release", 7),
    ]


def test_f06_ac06_changing_a_profile_sla_changes_the_json_with_no_code_change(
    profile: SiteProfile, tmp_path: Path
) -> None:
    changed = profile.model_copy(
        update={
            "stages": [
                s.model_copy(update={"sla_days": 9}) if s.key == "qc_testing" else s for s in profile.stages
            ],
            "reeval_sla_overrides": {**profile.reeval_sla_overrides, "sampling": 4},
        }
    )
    result = slas(changed, tmp_path, world_with_every_route())
    assert dict(result["RM1|B1|10000001"])["qc_testing"] == 9
    assert dict(result["RM1|B4|10000009"])["qc_testing"] == 27  # overridden for re-eval lots
    assert dict(result["RM1|B4|10000009"])["sampling"] == 4


def test_f06_ac06_a_profile_that_drops_a_stage_sla_drops_it_from_the_json(tmp_path: Path) -> None:
    profile = load_profile("site_a")
    changed = profile.model_copy(
        update={
            "stages": [
                s.model_copy(update={"sla_days": 0}) if s.key == "receipt" else s for s in profile.stages
            ]
        }
    )
    first_stage, _ = slas(changed, tmp_path, world_with_every_route())["RM1|B1|10000001"][0]
    assert first_stage == "sampling"


def test_f06_fr10_batch_stage_has_the_contract_columns_in_order(profile: SiteProfile, tmp_path: Path) -> None:
    world = World()
    world.receive("B1", "10000001", D(2026, 9, 1))
    world.write(tmp_path)
    transform(new_context(profile, tmp_path, snapshot_date=D(2026, 10, 12)))
    names = read_delta(tmp_path, "staging.batch_stage").column_names
    assert names[:8] == [
        "row_key",
        "stage_key",
        "stage_rule_id",
        "cycle_start_date",
        "ud_effective",
        "stage_sort",
        "current_stage_entry_date",
        "lims_rejected",
    ]
    assert names[19:21] == ["qa_release_exit", "applicable_sla_json"]
    assert names[-1] == "source_refs_json" and "inbound_light" in names


@pytest.mark.parametrize("bad", ["abc"])
def test_f06_fr05_json_is_compact_and_ordered(profile: SiteProfile, tmp_path: Path, bad: str) -> None:
    world = World()
    world.receive("B1", "10000001", D(2026, 9, 1))
    world.write(tmp_path)
    transform(new_context(profile, tmp_path, snapshot_date=D(2026, 10, 12)))
    text = read_delta(tmp_path, "staging.batch_stage")["applicable_sla_json"][0].as_py()
    assert text.startswith('[{"stage_key":"receipt","sla_days":10},')
