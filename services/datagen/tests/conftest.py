"""Fixtures for the generator's database tests: three throwaway, migrated source databases."""

from collections.abc import Callable

import pytest
from datagen.executor import Databases
from erp_sim.db import migrate as migrate_erp
from lims_sim.db import migrate as migrate_lims
from qms_sim.db import migrate as migrate_qms


@pytest.fixture(scope="session")
def source_databases(make_test_database: Callable[[str], str]) -> Databases:
    erp, lims, qms = (make_test_database(name) for name in ("datagen_erp", "datagen_lims", "datagen_qms"))
    migrate_erp(erp)
    migrate_lims(lims)
    migrate_qms(qms)
    return Databases(erp, lims, qms)
