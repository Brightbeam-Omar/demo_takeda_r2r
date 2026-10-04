"""The static world of a site: materials, suppliers, storage locations, campaigns (F05-FR-02, FR-10).

Everything comes from a seeded stream, so the same seed gives the same world. Names use only the generic
vocabulary of ``03-domain-model`` section 9. The story batches' materials are reserved: their numbers,
descriptions and molecule types are fixed here and the random builder skips them.
"""

import random
from dataclasses import dataclass

from r2r_core.profile import SiteProfile

from datagen.params import Params
from datagen.rng import stream

CAMPAIGNS = ("CMP-ALPHA", "CMP-BRAVO", "CMP-CEDAR", "CMP-DELTA", "CMP-EMBER")  # 03 section 9
LABS = ("External Lab A", "External Lab B")
COUNTRIES = ("IE", "DE", "FR", "CH", "US", "IN", "NL", "BE", "IT", "ES")

DRUG_SUBSTANCE_KINDS = ("Excipient", "API Intermediate", "Buffer Salt", "Reagent", "Solvent", "Stabiliser")
CONSUMABLE_KINDS = (
    "Filter Capsule 0.2µm",
    "Sterile Bag 5 L",
    "Tubing Set",
    "Sample Vial 20 mL",
    "Syringe Filter",
)

# Materials of the five story batches (F05-FR-06): number -> (description, molecule type, supplier).
STORY_MATERIALS: dict[str, tuple[str, str, str]] = {
    "RM10023": ("API Intermediate 004", "small_molecule", "SUP003"),
    "RM10031": ("Excipient 017", "peptide", "SUP007"),
    "RM10045": ("Buffer Salt 012", "large_molecule", "SUP011"),
    "RM10052": ("Excipient 021", "small_molecule", "SUP021"),
    "RM10067": ("API Intermediate 009", "small_molecule", "SUP030"),
}


@dataclass(frozen=True)
class Supplier:
    lifnr: str
    name: str
    country: str


@dataclass(frozen=True)
class Location:
    lgort: str
    name: str
    loctype: str  # onsite | 3pl


@dataclass(frozen=True)
class Material:
    matnr: str
    description: str
    mtart: str  # ROH raw / CONS consumable
    molecule: str
    klass: str  # drug_substance | consumable
    suppliers: tuple[str, ...]  # approved suppliers; the first is the usual one


@dataclass(frozen=True)
class World:
    materials: tuple[Material, ...]
    suppliers: tuple[Supplier, ...]
    locations: tuple[Location, ...]
    campaigns: tuple[str, ...] = CAMPAIGNS
    labs: tuple[str, ...] = LABS

    def material(self, matnr: str) -> Material:
        return next(m for m in self.materials if m.matnr == matnr)

    @property
    def onsite(self) -> tuple[Location, ...]:
        return tuple(loc for loc in self.locations if loc.loctype == "onsite")

    @property
    def threepl(self) -> tuple[Location, ...]:
        return tuple(loc for loc in self.locations if loc.loctype == "3pl")


LOCATIONS = (
    Location("0100", "Main Warehouse", "onsite"),
    Location("0110", "Cold Store", "onsite"),
    Location("0120", "Quarantine Bay", "onsite"),
    Location("0130", "QC Sampling Room", "onsite"),
    Location("0200", "3PL North", "3pl"),
    Location("0210", "3PL South", "3pl"),
)


def _molecule_labels(rng: random.Random, params: Params, count: int, reserved: list[str]) -> list[str]:
    """Molecule types for ``count`` materials in exact proportion, after the reserved ones are placed."""
    shares = params.mix.molecule_types
    wanted = {key: round(share * (count + len(reserved))) for key, share in shares.items()}
    labels: list[str] = []
    largest = max(wanted, key=lambda key: wanted[key])
    wanted[largest] += (count + len(reserved)) - sum(wanted.values())  # absorb rounding
    for key in reserved:
        wanted[key] -= 1
    for key, number in wanted.items():
        labels.extend([key] * number)
    rng.shuffle(labels)
    return labels[:count]


def _descriptions(rng: random.Random, kinds: tuple[str, ...], count: int, taken: set[str]) -> list[str]:
    """``count`` unique descriptions such as "Excipient 017", skipping the reserved ones."""
    counters = dict.fromkeys(kinds, 0)
    out: list[str] = []
    for index in range(count):
        kind = kinds[index % len(kinds)]
        while True:
            counters[kind] += 1
            text = f"{kind} {counters[kind]:03d}"
            if text not in taken:
                break
        out.append(text)
    rng.shuffle(out)
    return out


def build_world(profile: SiteProfile, params: Params, seed: int) -> World:
    rng = stream(seed, "world")
    suppliers = tuple(
        Supplier(f"SUP{n:03d}", f"Supplier {n:03d}", COUNTRIES[(n - 1) % len(COUNTRIES)])
        for n in range(1, params.volumes.suppliers + 1)
    )
    ids = [s.lifnr for s in suppliers]
    total = params.volumes.materials
    drug_count = round(total * params.mix.drug_substance_share)
    consumable_count = total - drug_count
    reserved_text = {description for description, _, _ in STORY_MATERIALS.values()}
    reserved_molecules = [molecule for _, molecule, _ in STORY_MATERIALS.values()]
    molecules = _molecule_labels(rng, params, total - len(STORY_MATERIALS), reserved_molecules)
    drug_descriptions = _descriptions(
        rng, DRUG_SUBSTANCE_KINDS, drug_count - len(STORY_MATERIALS), reserved_text
    )
    consumable_descriptions = _descriptions(rng, CONSUMABLE_KINDS, consumable_count, set())
    full_spec = {(pair.material, pair.supplier) for pair in profile.full_spec_pairs}

    def approved(matnr: str, usual: str | None = None) -> tuple[str, ...]:
        first = usual or rng.choice(ids)
        others = [i for i in ids if i != first]
        extra = rng.sample(others, rng.choice([0, 1, 1]))
        found = tuple([first, *extra])
        for material, supplier in full_spec:
            if material == matnr and supplier not in found:
                found = (*found, supplier)
        return found

    materials: list[Material] = []
    for number in range(1, drug_count + 1):
        matnr = f"RM{10000 + number}"
        if matnr in STORY_MATERIALS:
            description, molecule, supplier = STORY_MATERIALS[matnr]
            materials.append(
                Material(matnr, description, "ROH", molecule, "drug_substance", approved(matnr, supplier))
            )
        else:
            materials.append(
                Material(
                    matnr,
                    drug_descriptions.pop(),
                    "ROH",
                    molecules.pop(),
                    "drug_substance",
                    approved(matnr),
                )
            )
    for number in range(1, consumable_count + 1):
        matnr = f"CN{20000 + number}"
        materials.append(
            Material(
                matnr, consumable_descriptions.pop(), "CONS", molecules.pop(), "consumable", approved(matnr)
            )
        )
    return World(tuple(materials), suppliers, LOCATIONS)
