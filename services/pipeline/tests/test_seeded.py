"""T7: the stage engine against the seeded dataset (F06-AC-01, F06-AC-08). Needs Postgres (integration).

The test generates the F05 dataset into throwaway databases with its own ``expected_stages.csv`` (OQ-043), runs
extract and transform, and compares every row's stage with the generator's intended stage.
"""

import csv
import json
from collections import Counter
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pyarrow.compute as pc
import pytest
from datagen.executor import Databases
from datagen.generate import generate
from datagen.params import load_params
from erp_sim.db import migrate as migrate_erp
from lims_sim.db import migrate as migrate_lims
from qms_sim.db import migrate as migrate_qms
from r2r_core import clock
from r2r_core.clock import FixedClock
from r2r_core.profile import SiteProfile, load_profile
from r2r_pipeline.context import SourceDsns, new_context
from r2r_pipeline.extract import extract
from r2r_pipeline.lake import read_delta
from r2r_pipeline.transform import transform

pytestmark = pytest.mark.integration

STORY_BATCHES = {"B1042", "B2077", "B3150", "B4410", "B5003"}


@dataclass
class Seeded:
    lake: Path
    expected: dict[str, tuple[str, str]]  # row_key -> (intended stage, story id)
    actual: dict[str, str]  # row_key -> stage_key from the pipeline
    profile: SiteProfile


@pytest.fixture(scope="module")
def seeded(
    make_test_database: Callable[[str], str], tmp_path_factory: pytest.TempPathFactory
) -> Iterator[Seeded]:
    profile = load_profile("site_a")
    erp, lims, qms = (make_test_database(f"pipeline_seed_{name}") for name in ("erp", "lims", "qms"))
    migrate_erp(erp)
    migrate_lims(lims)
    migrate_qms(qms)
    artifacts, lake = tmp_path_factory.mktemp("artifacts"), tmp_path_factory.mktemp("lake")
    generate(profile, load_params(), profile.demo.seed, Databases(erp, lims, qms), artifacts)
    clock.set_clock_source(FixedClock(profile.demo.start_datetime.astimezone(UTC)))
    try:
        ctx = new_context(profile, lake, dsns=SourceDsns(erp, lims, qms))
        extract(ctx)
        transform(ctx)
    finally:
        clock.set_clock_source(None)
    with (artifacts / "expected_stages.csv").open(encoding="utf-8") as handle:
        expected = {
            row["row_key"]: (row["intended_stage"], row["story_id"]) for row in csv.DictReader(handle)
        }
    stage = read_delta(lake, "staging.batch_stage")
    actual = dict(zip(stage["row_key"].to_pylist(), stage["stage_key"].to_pylist(), strict=True))
    yield Seeded(lake, expected, actual, profile)


def mismatches(seeded: Seeded) -> list[str]:
    out = [
        f"{key}: expected {want}, got {seeded.actual.get(key)}"
        for key, (want, _) in sorted(seeded.expected.items())
        if seeded.actual.get(key) != want
    ]
    out += [f"{key}: not in the oracle" for key in sorted(set(seeded.actual) - set(seeded.expected))]
    return out


def test_f06_ac01_the_stage_engine_agrees_with_the_oracle(seeded: Seeded) -> None:
    wrong = mismatches(seeded)
    agreement = 1 - len(wrong) / len(seeded.expected)
    counts = Counter(seeded.actual.values())
    print(
        f"\nagreement {agreement:.2%} of {len(seeded.expected)} rows; stage counts {dict(sorted(counts.items()))}"
    )
    assert agreement >= 0.99, "\n".join(wrong)
    assert wrong == [], "\n".join(wrong)  # the aim is 100%; the spec's 99% is the floor


def test_f06_ac01_every_story_batch_is_exactly_right(seeded: Seeded) -> None:
    stories = {key: want for key, (want, story) in seeded.expected.items() if story}
    assert {key.split("|")[1] for key in stories} == STORY_BATCHES
    assert {key: seeded.actual[key] for key in stories} == stories


def test_f06_ac08_source_refs_for_b1042_name_its_lot_documents_and_sample(seeded: Seeded) -> None:
    key = next(k for k in seeded.expected if k.split("|")[1] == "B1042")
    stage = read_delta(seeded.lake, "staging.batch_stage")
    refs = json.loads(stage.filter(pc.equal(stage["row_key"], key))["source_refs_json"][0].as_py())
    material, batch, lot = key.split("|")
    assert refs["erp"]["mcha"] == f"{material}|{batch}"
    assert refs["erp"]["qals"] == lot
    documents = read_delta(seeded.lake, "staging.stg_mseg")
    wanted = documents.filter(pc.equal(documents["charg"], batch))["mblnr"].to_pylist()
    assert refs["erp"]["mseg"] == sorted(wanted) and wanted
    samples = read_delta(seeded.lake, "staging.stg_sample")
    sample_ids = samples.filter(pc.equal(samples["inspection_lot_no"], lot))["sample_id"].to_pylist()
    assert refs["lims"]["sample"] == max(sample_ids)


def test_f06_fr07_batch_flat_and_batch_stage_have_one_row_per_lot(seeded: Seeded) -> None:
    flat = read_delta(seeded.lake, "staging.batch_flat")
    stage = read_delta(seeded.lake, "staging.batch_stage")
    assert flat.num_rows == stage.num_rows == len(seeded.expected)
    assert len(set(flat["row_key"].to_pylist())) == flat.num_rows


def test_f06_fr07_the_demo_clock_instant_is_the_snapshot_date(seeded: Seeded) -> None:
    flat = read_delta(seeded.lake, "staging.batch_flat")
    needs = [d for d in flat["system_need_by_date"].to_pylist() if d is not None]
    assert needs and min(needs) >= datetime(2026, 10, 12, tzinfo=UTC).date()
