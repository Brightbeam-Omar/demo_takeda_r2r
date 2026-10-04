"""Fixtures for the pipeline tests."""

import sys
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from r2r_core import clock
from r2r_core.clock import FixedClock
from r2r_core.profile import SiteProfile, load_profile
from r2r_pipeline.context import SourceDsns

sys.path.insert(0, str(Path(__file__).parent))  # lets tests import fixture_world

DEMO_NOW = datetime(2026, 10, 12, 7, 0, tzinfo=UTC)


@pytest.fixture(scope="session")
def profile() -> SiteProfile:
    return load_profile("site_a")


@pytest.fixture
def demo_clock() -> Iterator[None]:
    """The demo clock fixed at the opening instant for the test."""
    clock.set_clock_source(FixedClock(DEMO_NOW))
    yield
    clock.set_clock_source(None)


@pytest.fixture(scope="session")
def source_dsns(make_test_database: Callable[[str], str]) -> SourceDsns:
    """Three migrated, empty source databases with one material, supplier, location and a received batch."""
    from erp_sim import events as erp_events
    from erp_sim import schemas as erp_schemas
    from erp_sim.db import migrate as migrate_erp
    from erp_sim.models import Lfa1, Mara, T001l
    from lims_sim.db import migrate as migrate_lims
    from qms_sim.db import migrate as migrate_qms
    from r2r_core.db import make_engine, make_session_factory

    erp, lims, qms = (make_test_database(f"pipeline_{name}") for name in ("erp", "lims", "qms"))
    migrate_erp(erp)
    migrate_lims(lims)
    migrate_qms(qms)
    clock.set_clock_source(FixedClock(DEMO_NOW))
    try:
        factory = make_session_factory(make_engine(erp))
        with factory() as session:
            session.add_all(
                [
                    Mara(
                        matnr="RM10001",
                        maktx="Excipient 001",
                        mtart="ROH",
                        zmolty="small_molecule",
                        zclass="drug_substance",
                    ),
                    Lfa1(lifnr="SUP001", name1="Supplier 001", land1="IE"),
                    T001l(lgort="0100", lgobe="Main Warehouse", zloctype="onsite"),
                ]
            )
            session.commit()
            erp_events.goods_receipt(
                session,
                erp_schemas.GoodsReceiptIn(
                    matnr="RM10001", charg="B1001", lifnr="SUP001", lgort="0100", menge=Decimal(100)
                ),
            )
            session.commit()
    finally:
        clock.set_clock_source(None)
    return SourceDsns(erp, lims, qms)
