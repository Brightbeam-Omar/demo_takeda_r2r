"""T3: ERP event functions [F04-FR-03, F04-FR-10, F04-AC-02, F04-AC-05]. Needs Postgres (integration).

The functions take no clock argument: they stamp `updated_at` with `r2r_core.clock.now()`.
"""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from erp_sim import events, schemas
from erp_sim.models import Counter, Mcha, Mchb, Mdez, Mseg, Qals, Zinbchk, ZinbchkItem
from r2r_core import clock
from r2r_core.clock import FixedClock
from r2r_core.errors import Conflict, Invalid
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

pytestmark = pytest.mark.integration

DEMO_NOW = datetime(2026, 10, 12, 7, 0, tzinfo=UTC)
TODAY = date(2026, 10, 12)  # site timezone: 08:00 local


def receive(session: Session, **overrides: object) -> dict[str, object]:
    body = {"matnr": "RM10001", "charg": "B1001", "lifnr": "SUP001", "lgort": "0100", "menge": Decimal(100)}
    return events.goods_receipt(session, schemas.GoodsReceiptIn(**{**body, **overrides}))


def stock(session: Session, charg: str = "B1001") -> dict[str, tuple[Decimal, Decimal, Decimal]]:
    rows = session.scalars(select(Mchb).where(Mchb.charg == charg)).all()
    return {r.lgort: (r.insme, r.speme, r.clabs) for r in rows}


def lot(session: Session, prueflos: str) -> Qals:
    found = session.get(Qals, prueflos)
    assert found is not None
    return found


# --- goods receipt -----------------------------------------------------------------------------


def test_f04_ac02_goods_receipt_creates_consistent_rows_stamped_with_the_demo_clock(
    factory: sessionmaker[Session],
) -> None:
    """F04-AC-02: GR for a new batch writes mseg 101, mchb, mcha, qals (01) and an open zinbchk."""
    with factory() as session:
        result = receive(session)
        session.commit()
    with factory() as session:
        batch = session.get(Mcha, ("RM10001", "B1001"))
        movement = session.scalars(select(Mseg)).one()
        stock_row = session.scalars(select(Mchb)).one()
        qals = session.scalars(select(Qals)).one()
        check = session.scalars(select(Zinbchk)).one()
        assert batch is not None
        assert (movement.bwart, movement.lgort, movement.umlgo, movement.menge) == ("101", "0100", None, 100)
        assert movement.budat == TODAY
        assert (stock_row.insme, stock_row.speme, stock_row.clabs) == (100, 0, 0)
        assert (qals.art, qals.pastrterm, qals.vcode) == ("01", TODAY, None)
        assert (check.prueflos, check.status, check.completed_on) == (qals.prueflos, "open", None)
        assert batch.zstat == ""
        for row in (batch, movement, stock_row, qals, check):
            assert row.updated_at == DEMO_NOW
    assert set(result) == {"mcha", "mseg", "mchb", "qals", "zinbchk"}


def test_f04_fr10_numbers_follow_the_contract_formats(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        receive(session)
        receive(session, charg="B1002")
        session.commit()
        docs = sorted(session.scalars(select(Mseg.mblnr)))
        lots = sorted(session.scalars(select(Qals.prueflos)))
    assert docs == ["4900000001", "4900000002"]
    assert lots == ["10000001", "10000002"]


def test_f04_fr10_explicit_numbers_are_used_and_later_allocation_skips_them(
    factory: sessionmaker[Session],
) -> None:
    with factory() as session:
        receive(session, mblnr="4900000001", prueflos="10000001")
        receive(session, charg="B1002")  # allocation would have given ...001 again
        session.commit()
        assert sorted(session.scalars(select(Mseg.mblnr))) == ["4900000001", "4900000002"]
        assert sorted(session.scalars(select(Qals.prueflos))) == ["10000001", "10000002"]


def test_f04_fr10_duplicate_batch_is_a_conflict_and_writes_nothing(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        receive(session)
        session.commit()
    with factory() as session, pytest.raises(Conflict):
        receive(session)
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Mseg)) == 1


def test_f04_fr10_duplicate_explicit_document_number_is_a_conflict(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        receive(session, mblnr="4900000009")
        session.commit()
    with factory() as session, pytest.raises(Conflict):
        receive(session, charg="B1002", mblnr="4900000009")


@pytest.mark.parametrize("field", ["matnr", "lifnr", "lgort"])
def test_f04_fr10_unknown_references_are_invalid(factory: sessionmaker[Session], field: str) -> None:
    with factory() as session, pytest.raises(Invalid, match=field.replace("matnr", "material")):
        receive(session, **{field: "NOPE"})


def test_f04_oq027_business_dates_can_be_given_and_updated_at_still_follows_the_clock(
    factory: sessionmaker[Session],
) -> None:
    """History is built by calling the same functions with the clock set to each simulated day."""
    day = datetime(2026, 8, 3, 7, 0, tzinfo=UTC)
    clock.set_clock_source(FixedClock(day))
    with factory() as session:
        receive(session, budat=date(2026, 8, 3), pastrterm=date(2026, 8, 4))
        session.commit()
        movement = session.scalars(select(Mseg)).one()
        assert movement.updated_at == day
        assert movement.budat == date(2026, 8, 3)
        assert session.scalars(select(Qals)).one().pastrterm == date(2026, 8, 4)


# --- goods receipt reversal --------------------------------------------------------------------


def test_f04_oq028_reversal_posts_102_and_leaves_batch_lot_and_check(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        receive(session)
        events.goods_receipt_reversal(session, schemas.ReversalIn(matnr="RM10001", charg="B1001"))
        session.commit()
        types = sorted(session.scalars(select(Mseg.bwart)))
        assert types == ["101", "102"]
        assert stock(session) == {}  # the empty stock row is gone
        assert session.get(Mcha, ("RM10001", "B1001")) is not None
        assert session.scalar(select(func.count()).select_from(Qals)) == 1
        assert session.scalar(select(func.count()).select_from(Zinbchk)) == 1
        reversal = session.scalars(select(Mseg).where(Mseg.bwart == "102")).one()
        assert (reversal.lgort, reversal.umlgo, reversal.menge) == ("0100", None, 100)


def test_f04_oq028_a_partial_reversal_keeps_the_rest_in_stock(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        receive(session)
        events.goods_receipt_reversal(
            session, schemas.ReversalIn(matnr="RM10001", charg="B1001", menge=Decimal(30))
        )
        session.commit()
        assert stock(session) == {"0100": (Decimal(70), Decimal(0), Decimal(0))}


def test_f04_oq028_cannot_reverse_what_was_not_received_or_already_reversed(
    factory: sessionmaker[Session],
) -> None:
    with factory() as session:
        receive(session)
        events.goods_receipt_reversal(session, schemas.ReversalIn(matnr="RM10001", charg="B1001"))
        session.commit()
    with factory() as session, pytest.raises(Invalid, match="nothing to reverse"):
        events.goods_receipt_reversal(session, schemas.ReversalIn(matnr="RM10001", charg="B1001"))
    with factory() as session, pytest.raises(Invalid, match="batch"):
        events.goods_receipt_reversal(session, schemas.ReversalIn(matnr="RM10001", charg="NOPE"))


def test_f04_oq028_cannot_reverse_stock_that_left_inspection(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        result = receive(session)
        prueflos = str(result["qals"]["prueflos"])  # type: ignore[index]
        events.usage_decision(session, schemas.UsageDecisionIn(prueflos=prueflos, vcode="A"))
        session.commit()
    with factory() as session, pytest.raises(Invalid, match="inspection"):
        events.goods_receipt_reversal(session, schemas.ReversalIn(matnr="RM10001", charg="B1001"))


# --- transfer ----------------------------------------------------------------------------------


def test_f04_fr03_transfer_moves_stock_in_the_same_bucket_and_posts_311(
    factory: sessionmaker[Session],
) -> None:
    with factory() as session:
        receive(session, lgort="0200")
        events.transfer(
            session, schemas.TransferIn(matnr="RM10001", charg="B1001", from_lgort="0200", to_lgort="0100")
        )
        session.commit()
        assert stock(session) == {"0100": (Decimal(100), Decimal(0), Decimal(0))}
        move = session.scalars(select(Mseg).where(Mseg.bwart == "311")).one()
        assert (move.lgort, move.umlgo, move.menge) == ("0200", "0100", 100)


def test_f04_fr03_partial_transfer_keeps_both_rows(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        receive(session, lgort="0200")
        events.transfer(
            session,
            schemas.TransferIn(
                matnr="RM10001", charg="B1001", from_lgort="0200", to_lgort="0100", menge=Decimal(40)
            ),
        )
        session.commit()
        assert stock(session) == {
            "0200": (Decimal(60), Decimal(0), Decimal(0)),
            "0100": (Decimal(40), Decimal(0), Decimal(0)),
        }


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"from_lgort": "0300"}, "no stock"),
        ({"to_lgort": "NOPE"}, "storage location"),
        ({"to_lgort": "0200"}, "differ"),
        ({"menge": Decimal(500)}, "only"),
    ],
)
def test_f04_fr03_invalid_transfers_are_rejected(
    factory: sessionmaker[Session], overrides: dict[str, object], message: str
) -> None:
    body = {"matnr": "RM10001", "charg": "B1001", "from_lgort": "0200", "to_lgort": "0100", **overrides}
    with factory() as session:
        receive(session, lgort="0200")
        with pytest.raises(Invalid, match=message):
            events.transfer(session, schemas.TransferIn(**body))


# --- inbound check -----------------------------------------------------------------------------


def test_f04_fr03_inbound_check_completes_with_a_date(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        result = receive(session)
        prueflos = str(result["qals"]["prueflos"])  # type: ignore[index]
        events.inbound_check(
            session, schemas.InboundCheckIn(prueflos=prueflos, status="passed", notes="visual ok")
        )
        session.commit()
        check = session.get(Zinbchk, prueflos)
        assert check is not None
        assert (check.status, check.completed_on, check.notes) == ("passed", TODAY, "visual ok")


def test_f04_fr03_inbound_check_needs_an_existing_lot_with_a_check(factory: sessionmaker[Session]) -> None:
    with factory() as session, pytest.raises(Invalid, match="lot"):
        events.inbound_check(session, schemas.InboundCheckIn(prueflos="19999999", status="passed"))


ITEMS = [
    schemas.InboundItemIn(check_code="PHYS", check_label="Physical evaluation", outcome="PASS"),
    schemas.InboundItemIn(check_code="QTY", check_label="Quantity received verification", outcome="FAIL"),
    schemas.InboundItemIn(check_code="RES", check_label="Results of analytical work", outcome="PENDING"),
]


def items_of(session: Session, prueflos: str) -> list[tuple[int, str, str]]:
    rows = session.scalars(
        select(ZinbchkItem).where(ZinbchkItem.prueflos == prueflos).order_by(ZinbchkItem.seq)
    ).all()
    return [(r.seq, r.check_code, r.outcome) for r in rows]


def test_f19_fr02_inbound_check_accepts_items_and_the_resolved_status(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        prueflos = str(receive(session)["qals"]["prueflos"])  # type: ignore[index]
        result = events.inbound_check(
            session, schemas.InboundCheckIn(prueflos=prueflos, status="resolved", items=ITEMS)
        )
        session.commit()
        check = session.get(Zinbchk, prueflos)
        assert check is not None
        assert (check.status, check.completed_on) == ("resolved", TODAY)
        assert items_of(session, prueflos) == [(1, "PHYS", "PASS"), (2, "QTY", "FAIL"), (3, "RES", "PENDING")]
        assert [i["outcome"] for i in result["zinbchk_item"]] == ["PASS", "FAIL", "PENDING"]  # type: ignore[index]


def test_f19_fr02_items_replace_the_previous_items_and_none_leaves_them(
    factory: sessionmaker[Session],
) -> None:
    with factory() as session:
        prueflos = str(receive(session, items=ITEMS)["qals"]["prueflos"])  # type: ignore[index]
        assert len(items_of(session, prueflos)) == 3
        events.inbound_check(session, schemas.InboundCheckIn(prueflos=prueflos, status="passed"))
        assert len(items_of(session, prueflos)) == 3  # no items given: unchanged
        events.inbound_check(
            session, schemas.InboundCheckIn(prueflos=prueflos, status="passed", items=ITEMS[:1])
        )
        session.commit()
        assert items_of(session, prueflos) == [(1, "PHYS", "PASS")]


def test_f19_fr02_goods_receipt_and_reeval_lot_accept_items(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        receive(session)
        result = events.reeval_lot(
            session,
            schemas.ReevalLotIn(matnr="RM10001", charg="B1001", inbound_check="resolved", items=ITEMS),
        )
        session.commit()
        prueflos = str(result["qals"]["prueflos"])  # type: ignore[index]
        check = session.get(Zinbchk, prueflos)
        assert check is not None
        assert check.status == "resolved"
        assert len(items_of(session, prueflos)) == 3


def test_f19_fr02_items_need_an_inbound_check(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        receive(session)
        with pytest.raises(Invalid, match="items"):
            events.reeval_lot(session, schemas.ReevalLotIn(matnr="RM10001", charg="B1001", items=ITEMS))


def test_f19_fr02_item_outcomes_are_checked() -> None:
    with pytest.raises(ValueError):
        schemas.InboundItemIn(check_code="X", check_label="X", outcome="MAYBE")  # type: ignore[arg-type]


# --- usage decision ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("A", (Decimal(0), Decimal(0), Decimal(100))),
        ("A4", (Decimal(0), Decimal(0), Decimal(100))),
        ("R", (Decimal(0), Decimal(100), Decimal(0))),
        ("X", (Decimal(100), Decimal(0), Decimal(0))),
    ],
)
def test_f04_oq028_usage_decision_moves_stock_buckets(
    factory: sessionmaker[Session], code: str, expected: tuple[Decimal, Decimal, Decimal]
) -> None:
    with factory() as session:
        result = receive(session)
        prueflos = str(result["qals"]["prueflos"])  # type: ignore[index]
        events.usage_decision(session, schemas.UsageDecisionIn(prueflos=prueflos, vcode=code))
        session.commit()
        assert lot(session, prueflos).vcode == code
        assert lot(session, prueflos).vdatum == TODAY
        assert stock(session) == {"0100": expected}


def test_f04_ac05_a_usage_decision_code_not_in_the_profile_is_invalid(factory: sessionmaker[Session]) -> None:
    """F04-AC-05: an unknown code is rejected (HTTP 422 in the API)."""
    with factory() as session:
        result = receive(session)
        prueflos = str(result["qals"]["prueflos"])  # type: ignore[index]
        with pytest.raises(Invalid, match="usage decision code"):
            events.usage_decision(session, schemas.UsageDecisionIn(prueflos=prueflos, vcode="Z9"))


def test_f04_fr03_a_lot_gets_one_usage_decision_only(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        result = receive(session)
        prueflos = str(result["qals"]["prueflos"])  # type: ignore[index]
        events.usage_decision(session, schemas.UsageDecisionIn(prueflos=prueflos, vcode="A"))
        with pytest.raises(Invalid, match="already"):
            events.usage_decision(session, schemas.UsageDecisionIn(prueflos=prueflos, vcode="R"))
    with factory() as session, pytest.raises(Invalid, match="lot"):
        events.usage_decision(session, schemas.UsageDecisionIn(prueflos="19999999", vcode="A"))


# --- re-evaluation lot -------------------------------------------------------------------------


def test_f04_oq028_reeval_lot_opens_a_09_lot_without_an_inbound_check_by_default(
    factory: sessionmaker[Session],
) -> None:
    with factory() as session:
        first = receive(session)
        events.usage_decision(
            session, schemas.UsageDecisionIn(prueflos=str(first["qals"]["prueflos"]), vcode="A")
        )  # type: ignore[index]
        events.reeval_lot(session, schemas.ReevalLotIn(matnr="RM10001", charg="B1001"))
        session.commit()
        lots = session.scalars(select(Qals).order_by(Qals.prueflos)).all()
        assert [lot_.art for lot_ in lots] == ["01", "09"]
        assert lots[1].pastrterm == TODAY
        assert session.scalar(select(func.count()).select_from(Zinbchk)) == 1  # only the first lot's check


def test_f04_oq028_reeval_lot_can_open_with_an_inbound_check(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        receive(session)
        result = events.reeval_lot(
            session, schemas.ReevalLotIn(matnr="RM10001", charg="B1001", inbound_check="passed")
        )
        session.commit()
        check = session.get(Zinbchk, str(result["qals"]["prueflos"]))  # type: ignore[index]
        assert check is not None
        assert (check.status, check.completed_on) == ("passed", TODAY)


def test_f04_oq028_reeval_lot_rules(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        receive(session)
        events.reeval_lot(session, schemas.ReevalLotIn(matnr="RM10001", charg="B1001"))
        with pytest.raises(Invalid, match="open re-evaluation"):
            events.reeval_lot(session, schemas.ReevalLotIn(matnr="RM10001", charg="B1001"))
        with pytest.raises(Invalid, match="batch"):
            events.reeval_lot(session, schemas.ReevalLotIn(matnr="RM10001", charg="NOPE"))


# --- stock block / unblock, hold, demand -------------------------------------------------------


def test_f04_oq028_stock_block_and_unblock_move_quantity_between_qi_and_blocked(
    factory: sessionmaker[Session],
) -> None:
    with factory() as session:
        receive(session)
        events.stock_block(session, schemas.StockMoveIn(matnr="RM10001", charg="B1001", menge=Decimal(25)))
        session.commit()
        assert stock(session) == {"0100": (Decimal(75), Decimal(25), Decimal(0))}
        events.stock_unblock(session, schemas.StockMoveIn(matnr="RM10001", charg="B1001"))
        session.commit()
        assert stock(session) == {"0100": (Decimal(100), Decimal(0), Decimal(0))}


def test_f04_oq028_stock_moves_need_enough_stock(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        receive(session)
        with pytest.raises(Invalid, match="quality inspection"):
            events.stock_block(
                session, schemas.StockMoveIn(matnr="RM10001", charg="B1001", menge=Decimal(500))
            )
        with pytest.raises(Invalid, match="blocked"):
            events.stock_unblock(session, schemas.StockMoveIn(matnr="RM10001", charg="B1001"))
        with pytest.raises(Invalid, match="batch"):
            events.stock_block(session, schemas.StockMoveIn(matnr="RM10001", charg="NOPE"))


def test_f04_oq028_stock_move_needs_a_location_when_stock_is_split(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        receive(session, lgort="0200")
        events.transfer(
            session,
            schemas.TransferIn(
                matnr="RM10001", charg="B1001", from_lgort="0200", to_lgort="0100", menge=Decimal(40)
            ),
        )
        with pytest.raises(Invalid, match="lgort"):
            events.stock_block(session, schemas.StockMoveIn(matnr="RM10001", charg="B1001"))
        events.stock_block(session, schemas.StockMoveIn(matnr="RM10001", charg="B1001", lgort="0100"))
        session.commit()
        assert stock(session)["0100"] == (Decimal(0), Decimal(40), Decimal(0))


def test_f04_oq028_hold_sets_and_clears_the_batch_status(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        receive(session)
        events.hold(session, schemas.HoldIn(matnr="RM10001", charg="B1001", hold=True))
        session.commit()
        batch = session.get(Mcha, ("RM10001", "B1001"))
        assert batch is not None
        assert batch.zstat == "H"
        events.hold(session, schemas.HoldIn(matnr="RM10001", charg="B1001", hold=False))
        session.commit()
        assert batch.zstat == ""
        with pytest.raises(Invalid, match="batch"):
            events.hold(session, schemas.HoldIn(matnr="RM10001", charg="NOPE", hold=True))


def test_f04_oq028_demand_creates_updates_and_closes(factory: sessionmaker[Session]) -> None:
    body = {
        "matnr": "RM10001",
        "campaign": "CMP-ALPHA",
        "requirement_date": date(2026, 12, 3),
        "quantity": Decimal(500),
    }
    with factory() as session:
        created = events.demand(session, schemas.DemandIn(**body))
        session.commit()
        demand_id = int(created["mdez"]["id"])  # type: ignore[index]
        row = session.get(Mdez, demand_id)
        assert row is not None
        assert (row.campaign, row.bdter, row.bdmng, row.is_open) == (
            "CMP-ALPHA",
            date(2026, 12, 3),
            500,
            True,
        )
        events.demand(
            session, schemas.DemandIn(**{**body, "id": demand_id, "requirement_date": date(2026, 11, 26)})
        )
        events.demand(session, schemas.DemandIn(**{**body, "id": demand_id, "is_open": False}))
        session.commit()
        session.refresh(row)
        assert (row.bdter, row.is_open) == (date(2026, 12, 3), False)
        assert session.scalar(select(func.count()).select_from(Mdez)) == 1
        with pytest.raises(Invalid, match="material"):
            events.demand(session, schemas.DemandIn(**{**body, "matnr": "NOPE"}))


def test_f04_fr10_counters_are_kept_per_sequence(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        receive(session)
        session.commit()
        names = set(session.scalars(select(Counter.name)))
    assert names == {"mblnr", "prueflos"}


def test_f05_oq039_results_recorded_sets_zresrec_without_a_usage_decision(
    factory: sessionmaker[Session],
) -> None:
    with factory() as session:
        prueflos = str(receive(session)["qals"]["prueflos"])  # type: ignore[index]
        later = datetime(2026, 10, 12, 9, 30, tzinfo=UTC)
        events.results_recorded(session, schemas.ResultsRecordedIn(prueflos=prueflos, at=later))
        session.commit()
        found = lot(session, prueflos)
        assert (found.zresrec, found.vcode, found.vdatum) == (later, None, None)
        with pytest.raises(Invalid, match="already recorded"):
            events.results_recorded(session, schemas.ResultsRecordedIn(prueflos=prueflos))


def test_f05_oq039_results_recorded_defaults_to_demo_now_and_checks_input(
    factory: sessionmaker[Session],
) -> None:
    with factory() as session:
        prueflos = str(receive(session)["qals"]["prueflos"])  # type: ignore[index]
        with pytest.raises(Invalid, match="timezone"):
            events.results_recorded(
                session, schemas.ResultsRecordedIn(prueflos=prueflos, at=datetime(2026, 10, 12, 9, 0))
            )
        with pytest.raises(Invalid, match="lot"):
            events.results_recorded(session, schemas.ResultsRecordedIn(prueflos="99999999"))
        events.results_recorded(session, schemas.ResultsRecordedIn(prueflos=prueflos))
        assert lot(session, prueflos).zresrec == DEMO_NOW


def test_f05_oq039_a_usage_decision_does_not_record_results(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        prueflos = str(receive(session)["qals"]["prueflos"])  # type: ignore[index]
        events.usage_decision(session, schemas.UsageDecisionIn(prueflos=prueflos, vcode="A"))
        assert lot(session, prueflos).zresrec is None


def test_f20_fr02_expedite_requested_sets_the_batch_dates(factory: sessionmaker[Session]) -> None:
    """F20-FR-02(d): the event writes mcha.zexprq and mcha.zexpdd; a later event replaces them."""
    with factory() as session:
        receive(session)
        out = events.expedite_requested(
            session,
            schemas.ExpediteRequestedIn(
                matnr="RM10001", charg="B1001", requested_on=date(2026, 9, 1), due_date=date(2026, 9, 20)
            ),
        )
        session.commit()
        assert out["mcha"]["zexprq"] == date(2026, 9, 1)
        batch = session.get(Mcha, ("RM10001", "B1001"))
        assert batch is not None
        assert (batch.zexprq, batch.zexpdd) == (date(2026, 9, 1), date(2026, 9, 20))
        events.expedite_requested(
            session,
            schemas.ExpediteRequestedIn(
                matnr="RM10001", charg="B1001", requested_on=date(2026, 9, 2), due_date=date(2026, 9, 25)
            ),
        )
        assert batch.zexpdd == date(2026, 9, 25)


def test_f20_fr02_expedite_due_date_may_not_precede_the_request_and_the_batch_must_exist(
    factory: sessionmaker[Session],
) -> None:
    with factory() as session:
        receive(session)
        with pytest.raises(Exception, match="due"):
            schemas.ExpediteRequestedIn(
                matnr="RM10001", charg="B1001", requested_on=date(2026, 9, 5), due_date=date(2026, 9, 1)
            )
        with pytest.raises(Invalid, match="batch"):
            events.expedite_requested(
                session,
                schemas.ExpediteRequestedIn(
                    matnr="RM10001", charg="NOPE", requested_on=date(2026, 9, 1), due_date=date(2026, 9, 2)
                ),
            )
