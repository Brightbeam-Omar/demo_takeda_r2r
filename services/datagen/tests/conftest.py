"""Fixtures for the generator's database tests: three throwaway, migrated source databases."""

from collections.abc import Callable

import pytest
from datagen.executor import Databases
from datagen.model import Plan
from datagen.params import Params, load_params
from datagen.planner import build_plan
from erp_sim.db import migrate as migrate_erp
from lims_sim.db import migrate as migrate_lims
from qms_sim.db import migrate as migrate_qms
from r2r_core.profile import SiteProfile, load_profile


@pytest.fixture(scope="session")
def source_databases(make_test_database: Callable[[str], str]) -> Databases:
    erp, lims, qms = (make_test_database(name) for name in ("datagen_erp", "datagen_lims", "datagen_qms"))
    migrate_erp(erp)
    migrate_lims(lims)
    migrate_qms(qms)
    return Databases(erp, lims, qms)


@pytest.fixture(scope="session")
def profile() -> SiteProfile:
    return load_profile("site_a")


@pytest.fixture(scope="session")
def params() -> Params:
    return load_params()


@pytest.fixture(scope="session")
def plan(profile: SiteProfile, params: Params) -> Plan:
    """The canonical plan (seed 4242), built once: it is pure, so tests only read it."""
    return build_plan(profile, params, 4242)
