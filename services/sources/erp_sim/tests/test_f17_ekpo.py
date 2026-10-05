"""F17 T2: open PO lines (`ekpo`) and how goods receipts close and reopen them [F17-FR-01]. Needs Postgres."""

from datetime import date
from decimal import Decimal

import pytest
from erp_sim import events, schemas
from erp_sim.models import Ekpo, Mseg
from r2r_core.errors import Invalid
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

pytestmark = pytest.mark.integration


def create_line(session: Session, **overrides: object) -> dict[str, object]:
    body = {"matnr": "RM10001", "lifnr": "SUP001", "lgort": "0100", "scheduled_date": date(2026, 10, 20)}
    return events.po_line_created(
        session, schemas.PoLineCreatedIn(**{**body, "menge": Decimal(100), **overrides})
    )


def receive(session: Session, **overrides: object) -> dict[str, object]:
    body = {"matnr": "RM10001", "charg": "B1001", "lifnr": "SUP001", "lgort": "0100", "menge": Decimal(100)}
    return events.goods_receipt(session, schemas.GoodsReceiptIn(**{**body, **overrides}))


def line(session: Session, ebeln: str, ebelp: str = "00010") -> Ekpo:
    found = session.get(Ekpo, (ebeln, ebelp))
    assert found is not None
    return found


def test_f17_fr01_po_line_created_numbers_and_stamps_an_open_line(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        first = create_line(session)
        second = create_line(session)
        session.commit()
    with factory() as session:
        a, b = first["ekpo"], second["ekpo"]
        assert isinstance(a, dict) and isinstance(b, dict)
        assert a["ebeln"] == "4500000001" and a["ebelp"] == "00010"
        assert b["ebeln"] == "4500000002"
        row = line(session, "4500000001")
        assert (row.is_open, row.eindt, row.menge, row.lgort) == (True, date(2026, 10, 20), 100, "0100")
        assert row.updated_at is not None


def test_f17_fr01_a_second_line_on_an_existing_po_steps_by_ten(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        create_line(session)
        added = create_line(session, ebeln="4500000001")
        session.commit()
    assert added["ekpo"]["ebelp"] == "00020"  # type: ignore[index]


def test_f17_fr01_po_line_closed_closes_and_rejects_a_second_close(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        create_line(session)
        events.po_line_closed(session, schemas.PoLineClosedIn(ebeln="4500000001", ebelp="00010"))
        assert line(session, "4500000001").is_open is False
        with pytest.raises(Invalid):
            events.po_line_closed(session, schemas.PoLineClosedIn(ebeln="4500000001", ebelp="00010"))


def test_f17_fr01_goods_receipt_with_a_po_reference_closes_the_line_and_stores_it(
    factory: sessionmaker[Session],
) -> None:
    with factory() as session:
        create_line(session)
        receive(session, ebeln="4500000001", ebelp="00010")
        session.commit()
    with factory() as session:
        assert line(session, "4500000001").is_open is False
        movement = session.scalars(select(Mseg)).one()
        assert (movement.ebeln, movement.ebelp) == ("4500000001", "00010")


def test_f17_fr01_goods_receipt_against_an_unknown_or_closed_line_is_invalid(
    factory: sessionmaker[Session],
) -> None:
    with factory() as session:
        with pytest.raises(Invalid):
            receive(session, ebeln="4599999999", ebelp="00010")
        create_line(session)
        events.po_line_closed(session, schemas.PoLineClosedIn(ebeln="4500000001", ebelp="00010"))
        with pytest.raises(Invalid):
            receive(session, ebeln="4500000001", ebelp="00010")


def test_f17_fr01_reversal_reopens_the_line_of_the_receipt_it_nets(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        create_line(session)
        receive(session, ebeln="4500000001", ebelp="00010")
        events.goods_receipt_reversal(session, schemas.ReversalIn(matnr="RM10001", charg="B1001"))
        session.commit()
    with factory() as session:
        assert line(session, "4500000001").is_open is True


def test_f17_fr01_reversal_of_a_receipt_without_a_po_reference_reopens_nothing(
    factory: sessionmaker[Session],
) -> None:
    with factory() as session:
        create_line(session)
        receive(session)
        events.goods_receipt_reversal(session, schemas.ReversalIn(matnr="RM10001", charg="B1001"))
        session.commit()
    with factory() as session:
        assert line(session, "4500000001").is_open is True  # was never closed
        assert session.scalars(select(Ekpo)).all().__len__() == 1
