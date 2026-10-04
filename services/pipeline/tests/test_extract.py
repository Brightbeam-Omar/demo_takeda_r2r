"""T3: extract with filters and freshness (F06-FR-01, F06-FR-02, F06-AC-03)."""

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pyarrow as pa
import pytest
from r2r_core.profile import SiteProfile
from r2r_pipeline.context import RunContext, SourceDsns, new_context
from r2r_pipeline.extract import extract, filter_qals, max_updated_at
from r2r_pipeline.lake import read_delta
from r2r_pipeline.schemas import STAGING, STAGING_SCHEMAS

NOW = datetime(2026, 10, 12, 7, 0, tzinfo=UTC)


def qals(rows: list[tuple[str, str, str | None]]) -> pa.Table:
    return pa.Table.from_pylist(
        [
            {
                "prueflos": lot, "art": art, "matnr": "RM1", "charg": "B1", "pastrterm": date(2026, 10, 1),
                "vcode": code, "vdatum": None, "zresrec": None, "updated_at": NOW,
            }
            for lot, art, code in rows
        ],
        schema=STAGING_SCHEMAS["stg_qals"],
    )  # fmt: skip


def test_f06_ac03_cancelled_ud_lots_and_other_lot_types_are_dropped() -> None:
    table = qals([("1", "01", None), ("2", "09", "A"), ("3", "01", "X"), ("4", "01", "R"), ("5", "03", None)])
    kept = filter_qals(table, ["X"])
    assert kept["prueflos"].to_pylist() == [
        "1",
        "2",
        "4",
    ]  # cancel (X) and type 03 are gone; reject (R) stays


def test_f06_fr01_every_table_of_the_contract_has_a_schema_with_updated_at() -> None:
    names = {name for tables in STAGING.values() for name in tables}
    assert names == {
        "stg_mara", "stg_lfa1", "stg_t001l", "stg_mcha", "stg_mchb", "stg_mseg", "stg_qals", "stg_zinbchk",
        "stg_mdez", "stg_sample", "stg_deviation", "stg_deviation_link",
    }  # fmt: skip
    assert all("updated_at" in schema.names for schema in STAGING_SCHEMAS.values())


def test_f06_fr01_max_updated_at_over_several_tables() -> None:
    schema = STAGING_SCHEMAS["stg_lfa1"]
    early, late = datetime(2026, 10, 1, tzinfo=UTC), datetime(2026, 10, 9, tzinfo=UTC)
    tables = [
        pa.Table.from_pylist(
            [{"lifnr": "S", "name1": "n", "land1": "IE", "updated_at": early}], schema=schema
        ),
        pa.Table.from_pylist(
            [{"lifnr": "T", "name1": "n", "land1": "IE", "updated_at": late}], schema=schema
        ),
        pa.Table.from_pylist([], schema=schema),
    ]
    assert max_updated_at(tables) == late
    assert max_updated_at([pa.Table.from_pylist([], schema=schema)]) is None


@pytest.mark.integration
def test_f06_fr01_extract_copies_every_source_table_and_records_freshness(
    tmp_path: Path, profile: SiteProfile, source_dsns: SourceDsns, demo_clock: None
) -> None:
    from erp_sim import events as erp_events
    from erp_sim import schemas as erp_schemas

    context: RunContext = new_context(profile, tmp_path, snapshot_date=date(2026, 10, 12), dsns=source_dsns)
    extract(context)
    for name in ("stg_mara", "stg_mseg", "stg_qals", "stg_sample", "stg_deviation_link", "stg_mdez"):
        assert read_delta(tmp_path, f"staging.{name}").schema == STAGING_SCHEMAS[name]
    assert read_delta(tmp_path, "staging.stg_mara").num_rows == 1
    assert read_delta(tmp_path, "staging.stg_mseg").column("menge").to_pylist() == [Decimal("100.000")]
    assert read_delta(tmp_path, "staging.stg_qals").num_rows == 1
    assert context.freshness["erp"]["max_updated_at"] == NOW.isoformat()
    assert context.freshness["lims"]["max_updated_at"] is None  # nothing in LIMS yet
    assert set(context.freshness) == {"erp", "lims", "qms"}
    assert context.freshness["erp"]["extracted_at"] == NOW.isoformat()
    # a lot closed with a cancel usage decision never reaches staging, and a second run overwrites
    from r2r_core.db import make_engine, make_session_factory

    with make_session_factory(make_engine(source_dsns.erp))() as session:
        result = erp_events.goods_receipt(
            session,
            erp_schemas.GoodsReceiptIn(
                matnr="RM10001", charg="B1002", lifnr="SUP001", lgort="0100", menge=Decimal(50)
            ),
        )
        erp_events.usage_decision(
            session, erp_schemas.UsageDecisionIn(prueflos=result["qals"]["prueflos"], vcode="X")
        )
        session.commit()
    extract(context)
    extract(context)
    assert read_delta(tmp_path, "staging.stg_qals").num_rows == 1  # the cancelled lot is gone
    assert read_delta(tmp_path, "staging.stg_mseg").num_rows == 2  # raw movements keep both batches
    assert read_delta(tmp_path, "staging.stg_mcha").num_rows == 2
