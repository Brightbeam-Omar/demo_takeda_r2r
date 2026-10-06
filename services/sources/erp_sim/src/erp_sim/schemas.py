"""Request bodies of the ERP event endpoints (F04-FR-03). Business dates default to the demo's today."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


Quantity = Field(gt=0, max_digits=13, decimal_places=3)


InboundOutcome = Literal["PASS", "FAIL", "PENDING", "NO", "COMP", "APRV", "DCPS"]


class InboundItemIn(Body):
    """One inbound sub-check (F19-FR-02). The position in the list is its sequence number."""

    check_code: str
    check_label: str
    outcome: InboundOutcome


class GoodsReceiptIn(Body):
    matnr: str
    charg: str
    lifnr: str
    lgort: str  # receiving storage location
    menge: Decimal = Quantity
    budat: date | None = None  # posting date
    licha: str | None = None  # supplier batch (default: the batch number)
    hsdat: date | None = None  # manufacture date
    vfdat: date | None = None  # expiry
    qnext: date | None = None  # next inspection (retest) date
    pastrterm: date | None = None  # lot start (default: posting date)
    mblnr: str | None = None  # explicit document number
    prueflos: str | None = None  # explicit inspection lot number
    ebeln: str | None = None  # purchase order line this receipt closes (give both or neither)
    ebelp: str | None = None
    items: list[InboundItemIn] | None = None  # inbound sub-checks of the open check (F19)


class ReversalIn(Body):
    matnr: str
    charg: str
    menge: Decimal | None = Field(default=None, gt=0, max_digits=13, decimal_places=3)  # default: all
    budat: date | None = None
    mblnr: str | None = None


class TransferIn(Body):
    matnr: str
    charg: str
    from_lgort: str
    to_lgort: str
    menge: Decimal | None = Field(default=None, gt=0, max_digits=13, decimal_places=3)  # default: all
    budat: date | None = None
    mblnr: str | None = None


class InboundCheckIn(Body):
    prueflos: str
    status: Literal["open", "passed", "resolved", "failed"]
    completed_on: date | None = None  # default: today when not open
    notes: str = ""
    items: list[InboundItemIn] | None = None  # replaces the lot's sub-checks; omit to leave them (F19)


class UsageDecisionIn(Body):
    prueflos: str
    vcode: str  # must be one of the profile's accept, reject or cancel codes
    vdatum: date | None = None


class ResultsRecordedIn(Body):
    prueflos: str
    at: datetime | None = None  # when the interface recorded the LIMS results (default: demo now)


class ReevalLotIn(Body):
    matnr: str
    charg: str
    pastrterm: date | None = None
    prueflos: str | None = None
    inbound_check: Literal["none", "open", "passed", "resolved", "failed"] = "none"
    completed_on: date | None = None
    items: list[InboundItemIn] | None = None  # needs an inbound check (F19)


class StockMoveIn(Body):
    matnr: str
    charg: str
    lgort: str | None = None  # needed only when the batch's stock is split over locations
    menge: Decimal | None = Field(default=None, gt=0, max_digits=13, decimal_places=3)  # default: all


class HoldIn(Body):
    matnr: str
    charg: str
    hold: bool


class DemandIn(Body):
    id: int | None = None  # omit to create; give it to update
    matnr: str
    campaign: str
    requirement_date: date
    quantity: Decimal = Quantity
    is_open: bool = True


class PoLineCreatedIn(Body):
    matnr: str
    lifnr: str
    lgort: str  # planned receiving location
    scheduled_date: date
    menge: Decimal = Quantity
    ebeln: str | None = None  # omit to open a new purchase order; give it to add a line to one
    ebelp: str | None = None


class PoLineClosedIn(Body):
    ebeln: str
    ebelp: str
