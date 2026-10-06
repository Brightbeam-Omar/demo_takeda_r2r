"""T4: transform SQL 10-48 and 60: batch_flat, flags and source refs (F06-FR-03, F06-FR-06, F06-FR-07)."""

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import duckdb
import pytest
from fixture_world import World
from r2r_core.profile import SiteProfile
from r2r_pipeline.context import RunContext, new_context
from r2r_pipeline.lake import read_delta
from r2r_pipeline.source_refs import build_source_refs
from r2r_pipeline.transform import load_staging, run_files, transform, transform_files

TODAY = date(2026, 10, 12)
D = date


def build(world: World, tmp_path: Path, profile: SiteProfile) -> tuple[duckdb.DuckDBPyConnection, RunContext]:
    world.write(tmp_path)
    ctx = new_context(profile, tmp_path, snapshot_date=TODAY)
    con = duckdb.connect()
    load_staging(con, ctx)
    run_files(con, ctx, lambda p: p.name[:2] < "50" or p.name.startswith("60"))
    return con, ctx


def rows(con: duckdb.DuckDBPyConnection, table: str = "batch_flat") -> dict[str, dict[str, Any]]:
    result = con.execute(f"SELECT * FROM {table}").to_arrow_table().to_pylist()
    return {r["row_key"]: r for r in result}


def test_f06_fr03_the_expected_sql_steps_exist() -> None:
    names = [p.name for p in transform_files()]
    assert names == [
        "10_stock.sql",
        "20_lots.sql",
        "30_lims.sql",
        "40_quality.sql",
        "45_demand.sql",
        "46_expected_deliveries.sql",
        "48_batch_flat.sql",
        "50_stage.sql.j2",
        "60_flags.sql",
        "90_batch_stage.sql",
    ]


def test_f06_fr03_a_received_lot_becomes_one_row_with_its_erp_facts(
    tmp_path: Path, profile: SiteProfile
) -> None:
    world = World()
    world.receive("B1", "10000001", D(2026, 10, 1))
    con, _ = build(world, tmp_path, profile)
    row = rows(con)["RM1|B1|10000001"]
    assert (row["material_desc"], row["supplier_name"], row["lot_type"], row["lot_start_date"]) == (
        "Excipient 001",
        "Supplier 001",
        "01",
        D(2026, 10, 1),
    )
    assert (row["gr_date"], row["received_location_type"], row["storage_location"], row["location_type"]) == (
        D(2026, 10, 1),
        "onsite",
        "0100",
        "onsite",
    )
    assert (row["stock_category"], row["inbound_check_status"], row["inbound_check_completed_date"]) == (
        "QI",
        "open",
        None,
    )
    assert (row["lims_status"], row["offsite_test"], row["sample_id"], row["transfer_to_site_date"]) == (
        "none",
        False,
        None,
        None,
    )
    assert (row["open_deviation_count"], row["closed_deviation_count"]) == (0, 0)
    assert row["next_inspection_date"] is None


def test_f06_ac04_a_same_day_reversal_leaves_the_batch_pending(tmp_path: Path, profile: SiteProfile) -> None:
    world = World()
    world.receive("B1", "10000001", D(2026, 10, 5))
    world.move("102", "B1", "0100", D(2026, 10, 5))
    world.rows["stg_mchb"].clear()  # the reversal takes the stock out
    con, _ = build(world, tmp_path, profile)
    row = rows(con)["RM1|B1|10000001"]
    assert row["gr_date"] is None and row["received_location_type"] is None
    assert row["storage_location"] == "0100"  # the last movement's destination


def test_f06_oq041_a_reversal_cancels_at_most_one_matching_receipt(
    tmp_path: Path, profile: SiteProfile
) -> None:
    world = World()
    world.receive("B1", "10000001", D(2026, 10, 5))
    world.move("101", "B1", "0100", D(2026, 10, 5))  # a second identical receipt the same day
    world.move("102", "B1", "0100", D(2026, 10, 5))  # cancels only one of them
    world.receive("B2", "10000002", D(2026, 10, 5))
    world.move(
        "102", "B2", "0100", D(2026, 10, 5), qty=40
    )  # a partial reversal does not match: stays as posted
    world.move("102", "B2", "0100", D(2026, 10, 6))  # a reversal on another day does not match either
    con, _ = build(world, tmp_path, profile)
    flat = rows(con)
    assert flat["RM1|B1|10000001"]["gr_date"] == D(2026, 10, 5)
    assert flat["RM1|B2|10000002"]["gr_date"] == D(2026, 10, 5)


def test_f06_fr07_a_3pl_receipt_and_its_transfer_to_site(tmp_path: Path, profile: SiteProfile) -> None:
    world = World()
    world.receive("B1", "10000001", D(2026, 10, 1), lgort="0200")
    world.move("311", "B1", "0200", D(2026, 10, 6), umlgo="0100")
    world.rows["stg_mchb"][0].update(lgort="0100")
    con, _ = build(world, tmp_path, profile)
    row = rows(con)["RM1|B1|10000001"]
    assert (row["received_location_type"], row["transfer_to_site_date"], row["storage_location"]) == (
        "3pl",
        D(2026, 10, 6),
        "0100",
    )


def test_f06_oq044_receipt_exit_only_for_a_passed_check_and_reeval_lots_are_onsite(
    tmp_path: Path, profile: SiteProfile
) -> None:
    world = World()
    for charg, lot, status in (
        ("B1", "10000001", "passed"),
        ("B2", "10000002", "failed"),
        ("B3", "10000003", "open"),
    ):
        world.receive(charg, lot, D(2026, 10, 1), lgort="0200" if charg == "B1" else "0100")
        world.check(lot, status, D(2026, 10, 3) if status != "open" else None)
    world.reeval("B1", "10000009", D(2026, 10, 8))
    con, _ = build(world, tmp_path, profile)
    flat = rows(con)
    assert flat["RM1|B1|10000001"]["inbound_check_completed_date"] == D(2026, 10, 3)
    assert flat["RM1|B2|10000002"]["inbound_check_completed_date"] is None  # failed: the receipt is not done
    assert flat["RM1|B3|10000003"]["inbound_check_completed_date"] is None
    reeval = flat["RM1|B1|10000009"]
    assert (reeval["lot_type"], reeval["received_location_type"], reeval["inbound_check_status"]) == (
        "09",
        "onsite",
        "none",
    )
    assert flat["RM1|B1|10000001"]["received_location_type"] == "3pl"  # its own initial lot is unchanged


def test_f06_oq044_storage_location_ties_and_stock_category_sums(
    tmp_path: Path, profile: SiteProfile
) -> None:
    world = World()
    world.receive("B1", "10000001", D(2026, 10, 1))
    world.rows["stg_mchb"].clear()
    world.stock("B1", "0300", insme=50)  # two locations with the same total: the lowest number wins
    world.stock("B1", "0100", speme=50)
    world.receive("B2", "10000002", D(2026, 10, 1))
    world.rows["stg_mchb"][-1].update(insme=Decimal(0), clabs=Decimal(100))
    con, _ = build(world, tmp_path, profile)
    flat = rows(con)
    assert (flat["RM1|B1|10000001"]["storage_location"], flat["RM1|B1|10000001"]["stock_category"]) == (
        "0100",
        "BLOCKED",
    )
    assert flat["RM1|B2|10000002"]["stock_category"] == "UNRESTRICTED"


from decimal import Decimal  # noqa: E402


def test_f06_ac03_a_cancelled_usage_decision_removes_the_lot_but_a_rejected_one_stays(
    tmp_path: Path, profile: SiteProfile
) -> None:
    world = World()
    for charg, lot, code in (("B1", "10000001", "X"), ("B2", "10000002", "R"), ("B3", "10000003", "A")):
        world.receive(charg, lot, D(2026, 10, 1))
        world.lot_field(lot, vcode=code, vdatum=D(2026, 10, 9))
    con, _ = build(world, tmp_path, profile)
    flat = rows(con)
    assert sorted(flat) == ["RM1|B2|10000002", "RM1|B3|10000003"]
    assert flat["RM1|B2|10000002"]["ud_code"] == "R"


def test_f06_fr07_the_latest_sample_decides_and_approval_is_a_site_local_date(
    tmp_path: Path, profile: SiteProfile
) -> None:
    world = World()
    world.receive("B1", "10000001", D(2026, 10, 1))
    world.sample("10000001", D(2026, 10, 3), status="rejected")
    world.sample(
        "10000001", D(2026, 10, 6), status="approved", approved_at=datetime(2026, 10, 11, 23, 30, tzinfo=UTC)
    )
    world.receive("B2", "10000002", D(2026, 10, 1))
    world.sample(
        "10000002", D(2026, 10, 3), status="registered", offsite=True, shipped=D(2026, 10, 4), charg="B2"
    )
    con, _ = build(world, tmp_path, profile)
    flat = rows(con)
    approved = flat["RM1|B1|10000001"]
    assert (approved["sample_id"], approved["lims_status"], approved["sample_collected_date"]) == (
        "S-0000002",
        "approved",
        D(2026, 10, 6),
    )
    assert approved["lims_approved_date"] == D(
        2026, 10, 12
    )  # 23:30Z on the 11th is 00:30 on the 12th in Dublin
    open_sample = flat["RM1|B2|10000002"]
    assert (
        open_sample["lims_status"],
        open_sample["offsite_test"],
        open_sample["external_lab"],
        open_sample["lims_approved_at"],
    ) == ("in_progress", True, "External Lab A", None)


def test_f06_fr06_need_by_is_the_earliest_open_line_on_or_after_the_snapshot_and_not_for_released_lots(
    tmp_path: Path, profile: SiteProfile
) -> None:
    world = World()
    world.receive("B1", "10000001", D(2026, 10, 1))
    world.receive("B2", "10000002", D(2026, 9, 1))
    world.lot_field("10000002", vcode="A", vdatum=D(2026, 9, 20))
    world.demand(1, D(2026, 10, 1), "CMP-OLD")  # before the snapshot date
    world.demand(2, D(2026, 11, 5), "CMP-LATE")
    world.demand(3, D(2026, 10, 20), "CMP-CLOSED", is_open=False)
    world.demand(5, D(2026, 10, 25), "CMP-BRAVO")
    world.demand(4, D(2026, 10, 25), "CMP-ALPHA")  # same date: the lowest id wins
    con, _ = build(world, tmp_path, profile)
    flat = rows(con)
    live, released = flat["RM1|B1|10000001"], flat["RM1|B2|10000002"]
    assert (live["system_need_by_date"], live["campaign"]) == (D(2026, 10, 25), "CMP-ALPHA")
    assert (released["system_need_by_date"], released["campaign"]) == (None, None)


def test_f06_fr07_deviation_counts_and_lights_flags(tmp_path: Path, profile: SiteProfile) -> None:
    world = World()
    world.receive("B1", "10000001", D(2026, 10, 1), hold=True)
    world.receive("B2", "10000002", D(2026, 10, 1))
    world.receive("B3", "10000003", D(2026, 10, 1))
    world.check("10000002", "passed", D(2026, 10, 2))
    world.check("10000003", "failed", D(2026, 10, 2))
    world.deviation("DEV-000001", "open", [("RM1", "B1")])
    world.deviation("DEV-000002", "closed", [("RM1", "B1"), ("RM1", "B2")])
    world.rows["stg_mchb"][0].update(insme=Decimal(0), speme=Decimal(100))
    world.lot_field("10000003", vcode="R", vdatum=D(2026, 10, 9))
    world.add(
        "stg_sample",
        sample_id="S-0000001",
        inspection_lot_no="10000003",
        material_no="RM1",
        batch_no="B3",
        collected_date=D(2026, 10, 3),
        offsite_test=True,
        shipped_date=D(2026, 10, 4),
        status="rejected",
    )
    con, _ = build(world, tmp_path, profile)
    flat, flags = rows(con), rows(con, "t_flags")
    assert (
        flat["RM1|B1|10000001"]["open_deviation_count"],
        flat["RM1|B1|10000001"]["closed_deviation_count"],
    ) == (1, 1)
    one, two, three = flags["RM1|B1|10000001"], flags["RM1|B2|10000002"], flags["RM1|B3|10000003"]
    assert (one["on_hold"], one["erp_blocked"], one["re_eval"], one["offsite"], one["full_spec"]) == (
        True,
        True,
        False,
        False,
        False,
    )
    assert (one["deviation_light"], two["deviation_light"], three["deviation_light"]) == (
        "red",
        "amber",
        "green",
    )
    assert (one["inbound_light"], two["inbound_light"], three["inbound_light"]) == ("red", "green", "red")
    assert (three["ud_rejected"], three["lims_rejected"], three["offsite"], one["ud_rejected"]) == (
        True,
        True,
        True,
        False,
    )


def test_f06_fr07_full_spec_comes_from_the_profile_pairs(tmp_path: Path, profile: SiteProfile) -> None:
    world = World()
    world.add(
        "stg_mara",
        matnr="RM10031",
        maktx="Excipient 017",
        mtart="ROH",
        zmolty="peptide",
        zclass="drug_substance",
    )
    world.add("stg_lfa1", lifnr="SUP007", name1="Supplier 007", land1="IE")
    for charg, lot, supplier in (("B2077", "10000001", "SUP007"), ("B2078", "10000002", "SUP1")):
        world.receive(charg, lot, D(2026, 10, 6), matnr="RM10031")
        world.rows["stg_mcha"][-1]["lifnr"] = supplier
    con, _ = build(world, tmp_path, profile)
    flags = rows(con, "t_flags")
    assert (flags["RM10031|B2077|10000001"]["full_spec"], flags["RM10031|B2078|10000002"]["full_spec"]) == (
        True,
        False,
    )


def test_f06_fr07_source_refs_list_every_document_and_the_sample(
    tmp_path: Path, profile: SiteProfile
) -> None:
    world = World()
    world.receive("B1", "10000001", D(2026, 10, 1))
    reversal = world.move("102", "B1", "0100", D(2026, 10, 1))
    world.sample("10000001", D(2026, 10, 3))
    world.deviation("DEV-000007", "open", [("RM1", "B1")])
    con, _ = build(world, tmp_path, profile)
    refs = build_source_refs(
        con.execute("SELECT * FROM batch_flat").to_arrow_table(),
        con.execute("SELECT * FROM stg_mseg").to_arrow_table(),
        con.execute("SELECT * FROM stg_deviation_link").to_arrow_table(),
    )
    import json

    parsed = json.loads(refs["RM1|B1|10000001"])
    assert parsed == {
        "erp": {"mcha": "RM1|B1", "qals": "10000001", "mseg": ["4900000001", reversal]},
        "lims": {"sample": "S-0000001"},
        "qms": {"deviation": ["DEV-000007"]},
    }


def test_f06_fr07_erp_results_recorded_at_is_the_lot_zresrec(tmp_path: Path, profile: SiteProfile) -> None:
    world = World()
    world.receive("B1", "10000001", D(2026, 10, 1))
    world.receive("B2", "10000002", D(2026, 10, 1))
    recorded = datetime(2026, 10, 9, 10, 0, tzinfo=UTC)
    world.lot_field("10000001", zresrec=recorded)
    con, _ = build(world, tmp_path, profile)
    flat = rows(con)
    assert flat["RM1|B1|10000001"]["erp_results_recorded_at"] == recorded
    assert flat["RM1|B2|10000002"]["erp_results_recorded_at"] is None


def test_f06_fr09_transform_is_a_plain_function_that_writes_batch_flat(
    tmp_path: Path, profile: SiteProfile
) -> None:
    world = World()
    world.receive("B1", "10000001", D(2026, 10, 1))
    world.write(tmp_path)
    transform(new_context(profile, tmp_path, snapshot_date=TODAY))
    table = read_delta(tmp_path, "staging.batch_flat")
    assert table.num_rows == 1
    expected = [
        "material_no",
        "material_desc",
        "material_class",
        "molecule_type",
        "supplier_id",
        "supplier_name",
        "supplier_batch",
        "batch_no",
        "batch_status_code",
        "inspection_lot_no",
        "lot_type",
        "lot_start_date",
        "storage_location",
        "location_type",
        "received_location_type",
        "stock_category",
        "gr_date",
        "transfer_to_site_date",
        "inbound_check_status",
        "inbound_check_completed_date",
        "sample_id",
        "sample_collected_date",
        "offsite_test",
        "external_lab",
        "sample_shipped_date",
        "lims_status",
        "lims_approved_date",
        "lims_approved_at",
        "ud_code",
        "ud_date",
        "erp_results_recorded_at",
        "campaign",
        "system_need_by_date",
        "open_deviation_count",
        "closed_deviation_count",
        "next_inspection_date",
        "need_by_at_release",
        "expedite_requested_on",
        "expedite_due_date",
    ]
    assert table.column_names == ["row_key", *expected]


@pytest.mark.parametrize("name", [p.name for p in transform_files()])
def test_f06_fr08_the_sql_files_are_named_in_lexical_order(name: str) -> None:
    assert name[:2].isdigit()


def test_f18_fr03g_the_batch_next_inspection_date_reaches_every_lot_of_the_batch(
    tmp_path: Path, profile: SiteProfile
) -> None:
    world = World()
    world.receive("B1", "10000001", D(2026, 10, 1), qnext=D(2027, 11, 3))
    world.reeval("B1", "10000002", D(2026, 10, 8))
    con, _ = build(world, tmp_path, profile)
    found = rows(con)
    assert found["RM1|B1|10000001"]["next_inspection_date"] == D(2027, 11, 3)
    assert found["RM1|B1|10000002"]["next_inspection_date"] == D(2027, 11, 3)


def test_f19_fr02_a_resolved_check_has_a_receipt_completion_date(
    tmp_path: Path, profile: SiteProfile
) -> None:
    world = World()
    for charg, lot, status in (("B1", "10000001", "resolved"), ("B2", "10000002", "passed")):
        world.receive(charg, lot, D(2026, 10, 1))
        world.check(lot, status, D(2026, 10, 3))
    con, _ = build(world, tmp_path, profile)
    flat = rows(con)
    assert flat["RM1|B1|10000001"]["inbound_check_status"] == "resolved"
    assert flat["RM1|B1|10000001"]["inbound_check_completed_date"] == D(2026, 10, 3)
    assert rows(con, "t_flags")["RM1|B1|10000001"]["inbound_light"] == "amber"


def _released(world: World, charg: str, lot: str, received: date, released: date) -> None:
    world.receive(charg, lot, received)
    world.lot_field(lot, vcode="A", vdatum=released)


def test_f20_fr02_need_by_at_release_is_the_earliest_demand_from_the_cycle_start_closed_lines_included(
    tmp_path: Path, profile: SiteProfile
) -> None:
    world = World()
    _released(world, "B1", "10000001", D(2026, 8, 3), D(2026, 8, 20))
    world.demand(1, D(2026, 7, 1), is_open=False)  # before the cycle: not this lot's demand
    world.demand(2, D(2026, 9, 15), is_open=False)  # closed when the lot was released: counts
    world.demand(3, D(2026, 10, 20))  # open, later: loses to the earlier line
    con, _ = build(world, tmp_path, profile)
    assert rows(con)["RM1|B1|10000001"]["need_by_at_release"] == D(2026, 9, 15)


def test_f20_fr02_need_by_at_release_is_only_for_released_lots_and_null_without_demand(
    tmp_path: Path, profile: SiteProfile
) -> None:
    world = World()
    _released(world, "B1", "10000001", D(2026, 8, 3), D(2026, 8, 20))
    world.receive("B2", "10000002", D(2026, 8, 3))  # not released
    world.demand(1, D(2026, 9, 15), is_open=False)
    world.stock("B3", "0100")
    con, _ = build(world, tmp_path, profile)
    found = rows(con)
    assert found["RM1|B2|10000002"]["need_by_at_release"] is None
    world2 = World()
    _released(world2, "B1", "10000001", D(2026, 8, 3), D(2026, 8, 20))
    con2, _ = build(world2, tmp_path, profile)
    assert rows(con2)["RM1|B1|10000001"]["need_by_at_release"] is None  # no demand line at all


def test_f20_fr02_a_re_evaluation_lot_anchors_on_its_own_lot_start(
    tmp_path: Path, profile: SiteProfile
) -> None:
    world = World()
    _released(world, "B1", "10000001", D(2026, 3, 2), D(2026, 3, 20))
    world.reeval("B1", "10000002", D(2026, 9, 1))
    world.lot_field("10000002", vcode="A", vdatum=D(2026, 9, 15))
    world.demand(1, D(2026, 4, 1), is_open=False)  # in the original cycle only
    world.demand(2, D(2026, 10, 5), is_open=False)
    con, _ = build(world, tmp_path, profile)
    found = rows(con)
    assert found["RM1|B1|10000001"]["need_by_at_release"] == D(2026, 4, 1)
    assert found["RM1|B1|10000002"]["need_by_at_release"] == D(2026, 10, 5)


def test_f20_fr02_expedite_facts_apply_to_every_lot_of_the_batch(
    tmp_path: Path, profile: SiteProfile
) -> None:
    world = World()
    world.receive("B1", "10000001", D(2026, 9, 1))
    world.reeval("B1", "10000002", D(2026, 10, 1))
    world.expedite("B1", D(2026, 9, 2), D(2026, 9, 20))
    world.receive("B2", "10000003", D(2026, 9, 1))
    con, _ = build(world, tmp_path, profile)
    found = rows(con)
    for lot in ("10000001", "10000002"):
        row = found[f"RM1|B1|{lot}"]
        assert (row["expedite_requested_on"], row["expedite_due_date"]) == (D(2026, 9, 2), D(2026, 9, 20))
    assert found["RM1|B2|10000003"]["expedite_due_date"] is None
