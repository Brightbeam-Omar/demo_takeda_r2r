"""ERP event functions: the one place that knows how to write consistent ERP rows (F04-FR-03).

Each function takes an open ``Session`` and a validated body, writes in that session (the caller commits, so
one event is one transaction), and returns the created or changed rows as dicts. They take **no clock
argument**: ``updated_at`` comes from ``r2r_core.clock.now()`` through the session (the demo clock over HTTP;
a ``FixedClock`` per simulated day when the generator calls them in-process). Business dates default to the
demo's today.

Stock buckets per batch and location: ``insme`` quality inspection (QI), ``speme`` blocked, ``clabs``
unrestricted. See ``04-data-contracts`` section 1.1.
"""

import functools
import os
from datetime import date
from decimal import Decimal
from typing import Any

from r2r_core import clock
from r2r_core.db import allocate_number, row_dict
from r2r_core.errors import Conflict, Invalid
from r2r_core.profile import UdCodes, load_profile
from sqlalchemy import select
from sqlalchemy.orm import Session

from erp_sim import schemas
from erp_sim.models import Counter, Lfa1, Mara, Mcha, Mchb, Mdez, Mseg, Qals, T001l, Zinbchk

ZERO = Decimal(0)


def _today(value: date | None) -> date:
    return value if value is not None else clock.today()


@functools.cache
def _ud_codes() -> UdCodes:
    return load_profile(os.environ.get("SITE_PROFILE", "site_a")).ud_codes


# --- lookups -----------------------------------------------------------------------------------


def _material(session: Session, matnr: str) -> Mara:
    found = session.get(Mara, matnr)
    if found is None:
        raise Invalid(f"unknown material {matnr}")
    return found


def _location(session: Session, lgort: str) -> T001l:
    found = session.get(T001l, lgort)
    if found is None:
        raise Invalid(f"unknown storage location (lgort) {lgort}")
    return found


def _batch(session: Session, matnr: str, charg: str) -> Mcha:
    found = session.get(Mcha, (matnr, charg))
    if found is None:
        raise Invalid(f"unknown batch {matnr}/{charg}")
    return found


def _lot(session: Session, prueflos: str) -> Qals:
    found = session.get(Qals, prueflos)
    if found is None:
        raise Invalid(f"unknown inspection lot {prueflos}")
    return found


def _stock_rows(session: Session, matnr: str, charg: str) -> list[Mchb]:
    query = select(Mchb).where(Mchb.matnr == matnr, Mchb.charg == charg).order_by(Mchb.lgort)
    return list(session.scalars(query))


def _total(stock: Mchb) -> Decimal:
    return stock.insme + stock.speme + stock.clabs


def _drop_if_empty(session: Session, stock: Mchb) -> None:
    if _total(stock) == 0:
        session.delete(stock)


# --- numbering ---------------------------------------------------------------------------------


def _document_number(session: Session, explicit: str | None) -> str:
    def taken(number: str) -> bool:
        return session.scalar(select(Mseg.mblnr).where(Mseg.mblnr == number)) is not None

    if explicit is not None:
        if taken(explicit):
            raise Conflict(f"material document {explicit} already exists")
        return explicit
    return allocate_number(session, Counter, "mblnr", lambda n: f"49{n:08d}", exists=taken)


def _lot_number(session: Session, explicit: str | None) -> str:
    def taken(number: str) -> bool:
        return session.get(Qals, number) is not None

    if explicit is not None:
        if taken(explicit):
            raise Conflict(f"inspection lot {explicit} already exists")
        return explicit
    return allocate_number(session, Counter, "prueflos", lambda n: f"1{n:07d}", exists=taken)


def _post(
    session: Session,
    *,
    bwart: str,
    key: tuple[str, str],
    lgort: str,
    umlgo: str | None,
    budat: date,
    menge: Decimal,
    explicit: str | None,
) -> Mseg:
    """Add one material document line (one line per document in Tier 1)."""
    line = Mseg(
        mblnr=_document_number(session, explicit),
        zeile="0001",
        bwart=bwart,
        matnr=key[0],
        charg=key[1],
        lgort=lgort,
        umlgo=umlgo,
        budat=budat,
        menge=menge,
    )
    session.add(line)
    return line


# --- events ------------------------------------------------------------------------------------


def goods_receipt(session: Session, body: schemas.GoodsReceiptIn) -> dict[str, Any]:
    """Receive a new batch: batch master, 101 posting, QI stock, initial lot 01 and an open inbound check."""
    _material(session, body.matnr)
    if session.get(Lfa1, body.lifnr) is None:
        raise Invalid(f"unknown supplier (lifnr) {body.lifnr}")
    _location(session, body.lgort)
    if session.get(Mcha, (body.matnr, body.charg)) is not None:
        raise Conflict(f"batch {body.matnr}/{body.charg} already exists")
    posted = _today(body.budat)
    batch = Mcha(
        matnr=body.matnr,
        charg=body.charg,
        lifnr=body.lifnr,
        licha=body.licha or body.charg,
        hsdat=body.hsdat,
        vfdat=body.vfdat,
        zstat="",
    )
    session.add(batch)
    session.flush()
    movement = _post(
        session,
        bwart="101",
        key=(body.matnr, body.charg),
        lgort=body.lgort,
        umlgo=None,
        budat=posted,
        menge=body.menge,
        explicit=body.mblnr,
    )
    stock = Mchb(
        matnr=body.matnr, charg=body.charg, lgort=body.lgort, insme=body.menge, speme=ZERO, clabs=ZERO
    )
    lot = Qals(
        prueflos=_lot_number(session, body.prueflos),
        art="01",
        matnr=body.matnr,
        charg=body.charg,
        pastrterm=body.pastrterm or posted,
        vcode=None,
        vdatum=None,
    )
    session.add_all([stock, lot])
    session.flush()
    check = Zinbchk(prueflos=lot.prueflos, status="open", completed_on=None, notes="")
    session.add(check)
    session.flush()
    return {
        "mcha": row_dict(batch),
        "mseg": row_dict(movement),
        "mchb": row_dict(stock),
        "qals": row_dict(lot),
        "zinbchk": row_dict(check),
    }


def goods_receipt_reversal(session: Session, body: schemas.ReversalIn) -> dict[str, Any]:
    """Post a 102 that takes received quantity back out of QI. Batch, lot and check rows stay."""
    _batch(session, body.matnr, body.charg)
    lines = list(session.scalars(select(Mseg).where(Mseg.matnr == body.matnr, Mseg.charg == body.charg)))
    received = sum((m.menge for m in lines if m.bwart == "101"), ZERO)
    reversed_ = sum((m.menge for m in lines if m.bwart == "102"), ZERO)
    net = received - reversed_
    if net <= 0:
        raise Invalid(f"nothing to reverse for batch {body.matnr}/{body.charg}")
    quantity = body.menge if body.menge is not None else net
    if quantity > net:
        raise Invalid(f"cannot reverse {quantity}: only {net} is received and not yet reversed")
    receipt = max((m for m in lines if m.bwart == "101"), key=lambda m: m.mblnr)
    stock = session.get(Mchb, (body.matnr, body.charg, receipt.lgort))
    in_inspection = stock.insme if stock is not None else ZERO
    if stock is None or in_inspection < quantity:
        raise Invalid(f"only {in_inspection} in quality inspection at {receipt.lgort}: stock has moved on")
    stock.insme -= quantity
    movement = _post(
        session,
        bwart="102",
        key=(body.matnr, body.charg),
        lgort=receipt.lgort,
        umlgo=None,
        budat=_today(body.budat),
        menge=quantity,
        explicit=body.mblnr,
    )
    changed = row_dict(stock)
    _drop_if_empty(session, stock)
    session.flush()
    return {"mseg": row_dict(movement), "mchb": changed}


def transfer(session: Session, body: schemas.TransferIn) -> dict[str, Any]:
    """Post a 311 that moves stock between locations, keeping each stock bucket."""
    if body.from_lgort == body.to_lgort:
        raise Invalid("from_lgort and to_lgort must differ")
    _batch(session, body.matnr, body.charg)
    _location(session, body.to_lgort)
    source = session.get(Mchb, (body.matnr, body.charg, body.from_lgort))
    if source is None:
        raise Invalid(f"no stock of {body.matnr}/{body.charg} at {body.from_lgort}")
    quantity = body.menge if body.menge is not None else _total(source)
    if quantity > _total(source):
        raise Invalid(f"only {_total(source)} in stock at {body.from_lgort}")
    target = session.get(Mchb, (body.matnr, body.charg, body.to_lgort))
    if target is None:
        target = Mchb(
            matnr=body.matnr, charg=body.charg, lgort=body.to_lgort, insme=ZERO, speme=ZERO, clabs=ZERO
        )
        session.add(target)
    remaining = quantity
    for bucket in ("insme", "speme", "clabs"):
        moved = min(remaining, getattr(source, bucket))
        setattr(source, bucket, getattr(source, bucket) - moved)
        setattr(target, bucket, getattr(target, bucket) + moved)
        remaining -= moved
    movement = _post(
        session,
        bwart="311",
        key=(body.matnr, body.charg),
        lgort=body.from_lgort,
        umlgo=body.to_lgort,
        budat=_today(body.budat),
        menge=quantity,
        explicit=body.mblnr,
    )
    changed = {"from": row_dict(source), "to": row_dict(target)}
    _drop_if_empty(session, source)
    session.flush()
    return {"mseg": row_dict(movement), "mchb": changed}


def inbound_check(session: Session, body: schemas.InboundCheckIn) -> dict[str, Any]:
    _lot(session, body.prueflos)
    check = session.get(Zinbchk, body.prueflos)
    if check is None:
        raise Invalid(f"inspection lot {body.prueflos} has no inbound check")
    check.status = body.status
    check.completed_on = None if body.status == "open" else _today(body.completed_on)
    check.notes = body.notes
    session.flush()
    return {"zinbchk": row_dict(check)}


def usage_decision(session: Session, body: schemas.UsageDecisionIn) -> dict[str, Any]:
    """Close a lot with a usage decision; QI stock follows: accept to unrestricted, reject to blocked."""
    codes = _ud_codes()
    allowed = [*codes.accept, *codes.reject, *codes.cancel]
    if body.vcode not in allowed:
        listed = ", ".join(allowed)
        raise Invalid(f"{body.vcode!r} is not a usage decision code of the site profile ({listed})")
    lot = _lot(session, body.prueflos)
    if lot.vcode is not None:
        raise Invalid(f"inspection lot {body.prueflos} already has a usage decision ({lot.vcode})")
    lot.vcode = body.vcode
    lot.vdatum = _today(body.vdatum)
    rows = _stock_rows(session, lot.matnr, lot.charg)
    for stock in rows:
        if body.vcode in codes.accept:
            stock.clabs += stock.insme
            stock.insme = ZERO
        elif body.vcode in codes.reject:
            stock.speme += stock.insme
            stock.insme = ZERO
    session.flush()
    return {"qals": row_dict(lot), "mchb": [row_dict(s) for s in rows]}


def results_recorded(session: Session, body: schemas.ResultsRecordedIn) -> dict[str, Any]:
    """The interface recorded the LIMS results of a lot in the ERP (``qals.zresrec``). No usage decision."""
    lot = _lot(session, body.prueflos)
    if lot.zresrec is not None:
        raise Invalid(f"results of inspection lot {body.prueflos} were already recorded")
    recorded = body.at if body.at is not None else clock.now()
    if recorded.tzinfo is None:
        raise Invalid("at must include a timezone offset")
    lot.zresrec = recorded
    session.flush()
    return {"qals": row_dict(lot)}


def reeval_lot(session: Session, body: schemas.ReevalLotIn) -> dict[str, Any]:
    """Open a re-evaluation lot (09) on an existing batch. An inbound check row exists only if asked for."""
    _batch(session, body.matnr, body.charg)
    open_lots = session.scalars(
        select(Qals).where(
            Qals.matnr == body.matnr, Qals.charg == body.charg, Qals.art == "09", Qals.vcode.is_(None)
        )
    ).first()
    if open_lots is not None:
        raise Invalid(f"batch {body.matnr}/{body.charg} already has an open re-evaluation lot")
    lot = Qals(
        prueflos=_lot_number(session, body.prueflos),
        art="09",
        matnr=body.matnr,
        charg=body.charg,
        pastrterm=_today(body.pastrterm),
        vcode=None,
        vdatum=None,
    )
    session.add(lot)
    session.flush()
    result: dict[str, Any] = {"qals": row_dict(lot)}
    if body.inbound_check != "none":
        done = None if body.inbound_check == "open" else _today(body.completed_on)
        check = Zinbchk(prueflos=lot.prueflos, status=body.inbound_check, completed_on=done, notes="")
        session.add(check)
        session.flush()
        result["zinbchk"] = row_dict(check)
    return result


def _single_stock(session: Session, body: schemas.StockMoveIn) -> Mchb:
    _batch(session, body.matnr, body.charg)
    rows = _stock_rows(session, body.matnr, body.charg)
    if body.lgort is not None:
        rows = [r for r in rows if r.lgort == body.lgort]
    if not rows:
        raise Invalid(f"no stock for batch {body.matnr}/{body.charg}")
    if len(rows) > 1:
        raise Invalid(f"stock is split over {', '.join(r.lgort for r in rows)}: give lgort")
    return rows[0]


def stock_block(session: Session, body: schemas.StockMoveIn) -> dict[str, Any]:
    """Move quantity from quality inspection to blocked, without a usage decision."""
    stock = _single_stock(session, body)
    quantity = body.menge if body.menge is not None else stock.insme
    if quantity > stock.insme:
        raise Invalid(f"only {stock.insme} in quality inspection at {stock.lgort}")
    stock.insme -= quantity
    stock.speme += quantity
    session.flush()
    return {"mchb": row_dict(stock)}


def stock_unblock(session: Session, body: schemas.StockMoveIn) -> dict[str, Any]:
    """Move quantity from blocked back to quality inspection."""
    stock = _single_stock(session, body)
    quantity = body.menge if body.menge is not None else stock.speme
    if quantity > stock.speme or quantity == 0:
        raise Invalid(f"only {stock.speme} blocked at {stock.lgort}")
    stock.speme -= quantity
    stock.insme += quantity
    session.flush()
    return {"mchb": row_dict(stock)}


def hold(session: Session, body: schemas.HoldIn) -> dict[str, Any]:
    batch = _batch(session, body.matnr, body.charg)
    batch.zstat = "H" if body.hold else ""
    session.flush()
    return {"mcha": row_dict(batch)}


def demand(session: Session, body: schemas.DemandIn) -> dict[str, Any]:
    """Create or update an MRP demand line. Closing a demand is ``is_open=false``."""
    _material(session, body.matnr)
    row = session.get(Mdez, body.id) if body.id is not None else None
    if row is None:
        if body.id is not None:
            number = body.id
        else:
            number = int(
                allocate_number(
                    session, Counter, "mdez", str, exists=lambda n: session.get(Mdez, int(n)) is not None
                )
            )
        row = Mdez(id=number)
        session.add(row)
    row.matnr, row.campaign = body.matnr, body.campaign
    row.bdter, row.bdmng, row.is_open = body.requirement_date, body.quantity, body.is_open
    session.flush()
    return {"mdez": row_dict(row)}
