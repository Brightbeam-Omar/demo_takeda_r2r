"""F17 T4 [TDD]: expected deliveries (open PO lines) in transform and publish [F17-FR-03, F17-AC-01]."""

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from fixture_world import World
from r2r_core.profile import SiteProfile
from r2r_pipeline.lake import read_delta
from r2r_pipeline.schemas import EXPECTED_DELIVERIES_SCHEMA
from test_publish import run_all

D = date


def deliveries(lake: Path) -> list[dict[str, Any]]:
    return read_delta(lake, "published.expected_deliveries_v").to_pylist()


@pytest.fixture
def world() -> World:
    w = World()
    w.receive("B1", "10000001", D(2026, 10, 1))
    w.demand(1, D(2026, 11, 20), campaign="CMP-BRAVO")
    w.po_line("4500000001", D(2026, 10, 20))
    w.po_line("4500000002", D(2026, 10, 9), lgort="0200")  # overdue, planned into the 3PL
    w.po_line("4500000003", D(2026, 10, 25), is_open=False)  # closed by a receipt
    w.po_line("4500000002", D(2026, 10, 30), ebelp="00020")
    return w


@pytest.mark.usefixtures("demo_clock")
def test_f17_fr03_only_open_lines_are_published_with_the_contract_columns(
    world: World, tmp_path: Path, profile: SiteProfile
) -> None:
    ctx = run_all(world, tmp_path, profile)
    rows = deliveries(tmp_path)
    assert [(r["ebeln"], r["ebelp"]) for r in rows] == [
        ("4500000001", "00010"), ("4500000002", "00010"), ("4500000002", "00020"),
    ]  # fmt: skip
    assert list(rows[0]) == [*EXPECTED_DELIVERIES_SCHEMA.names, "run_id"]
    assert {r["run_id"] for r in rows} == {ctx.run_id}
    first = rows[0]
    assert (first["material_no"], first["material_desc"], first["molecule_type"]) == (
        "RM1", "Excipient 001", "small_molecule",
    )  # fmt: skip
    assert (first["supplier_id"], first["supplier_name"], first["campaign"]) == (
        "SUP1", "Supplier 001", "CMP-BRAVO",
    )  # fmt: skip
    assert (first["scheduled_date"], first["quantity"]) == (D(2026, 10, 20), Decimal("100.000"))
    assert (first["planned_location"], first["planned_location_type"]) == ("0100", "onsite")


@pytest.mark.usefixtures("demo_clock")
def test_f17_fr03_overdue_means_the_scheduled_date_is_before_the_snapshot_date(
    world: World, tmp_path: Path, profile: SiteProfile
) -> None:
    run_all(world, tmp_path, profile)  # the demo clock is 12 Oct 2026
    overdue = {(r["ebeln"], r["ebelp"]): r["overdue"] for r in deliveries(tmp_path)}
    assert overdue == {
        ("4500000001", "00010"): False,
        ("4500000002", "00010"): True,
        ("4500000002", "00020"): False,
    }
    [late] = [r for r in deliveries(tmp_path) if r["planned_location_type"] == "3pl"]
    assert late["ebeln"] == "4500000002"


@pytest.mark.usefixtures("demo_clock")
def test_f17_fr03_no_open_lines_publishes_an_empty_object(tmp_path: Path, profile: SiteProfile) -> None:
    w = World()
    w.receive("B1", "10000001", D(2026, 10, 1))
    run_all(w, tmp_path, profile)
    assert deliveries(tmp_path) == []


@pytest.mark.usefixtures("demo_clock")
def test_f17_fr04_the_stage_reference_publishes_show_card(
    world: World, tmp_path: Path, profile: SiteProfile
) -> None:
    run_all(world, tmp_path, profile)
    cards = {
        r["stage_key"]: r["show_card"]
        for r in read_delta(tmp_path, "published.stage_reference_v").to_pylist()
    }
    assert cards["pending"] is False
    assert all(shown for key, shown in cards.items() if key != "pending")
