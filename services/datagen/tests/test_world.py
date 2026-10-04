"""T2: world builder (F05-FR-02, FR-10, AC-06 vocabulary)."""

from collections import Counter

import pytest
from datagen.params import load_params
from datagen.world import STORY_MATERIALS, World, build_world
from r2r_core.profile import load_profile


@pytest.fixture(scope="module")
def world() -> World:
    return build_world(load_profile("site_a"), load_params(), 4242)


def test_f05_fr02_world_volumes(world: World) -> None:
    assert len(world.materials) == 300
    assert len(world.suppliers) == 40
    assert len(world.locations) == 6
    assert len(world.onsite) == 4
    assert len(world.threepl) == 2
    classes = Counter(m.klass for m in world.materials)
    assert classes["drug_substance"] == 255
    assert classes["consumable"] == 45
    assert world.campaigns == ("CMP-ALPHA", "CMP-BRAVO", "CMP-CEDAR", "CMP-DELTA", "CMP-EMBER")


def test_f05_fr02_molecule_split_is_55_25_20(world: World) -> None:
    molecules = Counter(m.molecule for m in world.materials)
    assert molecules == {"small_molecule": 165, "large_molecule": 75, "peptide": 60}


def test_f05_fr10_numbers_and_descriptions_are_generic_and_unique(world: World) -> None:
    assert len({m.matnr for m in world.materials}) == 300
    assert len({m.description for m in world.materials}) == 300
    for material in world.materials:
        assert material.matnr.startswith("RM1" if material.klass == "drug_substance" else "CN2")
    assert {s.name for s in world.suppliers} == {f"Supplier {n:03d}" for n in range(1, 41)}


def test_f05_fr06_story_materials_are_reserved_exactly(world: World) -> None:
    for matnr, (description, molecule, supplier) in STORY_MATERIALS.items():
        material = world.material(matnr)
        assert (material.description, material.molecule) == (description, molecule)
        assert material.suppliers[0] == supplier
        assert material.klass == "drug_substance"
    assert "SUP007" in world.material("RM10031").suppliers  # the full-spec pair of the profile


def test_f05_fr09_same_seed_same_world_other_seed_other_world(world: World) -> None:
    profile, params = load_profile("site_a"), load_params()
    assert build_world(profile, params, 4242) == world
    assert build_world(profile, params, 7) != world
