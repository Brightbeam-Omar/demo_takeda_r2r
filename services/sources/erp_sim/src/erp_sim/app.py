"""ERP simulator API (port 8101): open reads, token-guarded scenario writes."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from r2r_core.db import row_dict
from r2r_core.web import add_event_routes, health_router, install_error_handlers, require_scenario_token
from sqlalchemy import select
from sqlalchemy.orm import Session

from erp_sim import events, schemas
from erp_sim.db import get_session
from erp_sim.models import Mara, Mcha, Mchb, Mseg, Qals, Zinbchk

SessionDep = Annotated[Session, Depends(get_session, scope="function")]

app = FastAPI(
    title="ERP simulator",
    description="SAP-shaped ERP stand-in. `/events/*` are scenario writes (`X-Scenario-Token`).",
)
install_error_handlers(app)
app.include_router(health_router("erp-sim"))


# --- reads -------------------------------------------------------------------------------------


@app.get("/materials", tags=["read"])
def materials(session: SessionDep) -> list[dict[str, Any]]:
    return [row_dict(m) for m in session.scalars(select(Mara).order_by(Mara.matnr))]


@app.get("/batches/{matnr}/{charg}", tags=["read"])
def batch(matnr: str, charg: str, session: SessionDep) -> dict[str, Any]:
    found = session.get(Mcha, (matnr, charg))
    if found is None:
        raise HTTPException(status_code=404, detail=f"unknown batch {matnr}/{charg}")

    def rows(model: Any, order_by: Any) -> list[dict[str, Any]]:
        query = select(model).where(model.matnr == matnr, model.charg == charg).order_by(order_by)
        return [row_dict(r) for r in session.scalars(query)]

    return {
        "batch": row_dict(found),
        "stock": rows(Mchb, Mchb.lgort),
        "movements": rows(Mseg, Mseg.mblnr),
        "lots": rows(Qals, Qals.prueflos),
    }


@app.get("/lots/{prueflos}", tags=["read"])
def lot(prueflos: str, session: SessionDep) -> dict[str, Any]:
    found = session.get(Qals, prueflos)
    if found is None:
        raise HTTPException(status_code=404, detail=f"unknown inspection lot {prueflos}")
    check = session.get(Zinbchk, prueflos)
    return {"lot": row_dict(found), "inbound_check": row_dict(check) if check is not None else None}


# --- scenario writes ---------------------------------------------------------------------------

writes = APIRouter(prefix="/events", tags=["scenario events"], dependencies=[Depends(require_scenario_token)])


add_event_routes(
    writes,
    [
        ("/goods-receipt", schemas.GoodsReceiptIn, events.goods_receipt),
        ("/goods-receipt-reversal", schemas.ReversalIn, events.goods_receipt_reversal),
        ("/transfer", schemas.TransferIn, events.transfer),
        ("/inbound-check", schemas.InboundCheckIn, events.inbound_check),
        ("/usage-decision", schemas.UsageDecisionIn, events.usage_decision),
        ("/reeval-lot", schemas.ReevalLotIn, events.reeval_lot),
        ("/results-recorded", schemas.ResultsRecordedIn, events.results_recorded),
        ("/stock-block", schemas.StockMoveIn, events.stock_block),
        ("/stock-unblock", schemas.StockMoveIn, events.stock_unblock),
        ("/hold", schemas.HoldIn, events.hold),
        ("/demand", schemas.DemandIn, events.demand),
        ("/po-line-created", schemas.PoLineCreatedIn, events.po_line_created),
        ("/po-line-closed", schemas.PoLineClosedIn, events.po_line_closed),
    ],
    get_session,
)
app.include_router(writes)
