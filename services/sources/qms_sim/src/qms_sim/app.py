"""QMS simulator API (port 8103): open reads, token-guarded scenario writes."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from r2r_core.db import row_dict
from r2r_core.web import add_event_routes, health_router, install_error_handlers, require_scenario_token
from sqlalchemy import select
from sqlalchemy.orm import Session

from qms_sim import events, schemas
from qms_sim.db import get_session
from qms_sim.events import change_links_of, links_of
from qms_sim.models import ChangeControl, ChangeControlLink, Deviation, DeviationLink

SessionDep = Annotated[Session, Depends(get_session, scope="function")]

app = FastAPI(
    title="QMS simulator",
    description="QMS stand-in. `/events/*` are scenario writes (`X-Scenario-Token`).",
)
install_error_handlers(app)
app.include_router(health_router("qms-sim"))


def _with_links(session: Session, deviation: Deviation) -> dict[str, Any]:
    links = [row_dict(link) for link in links_of(session, deviation.deviation_no)]
    return {**row_dict(deviation), "links": links}


@app.get("/deviations", tags=["read"])
def deviations(session: SessionDep, batch_no: str | None = None) -> list[dict[str, Any]]:
    query = select(Deviation).order_by(Deviation.deviation_no)
    if batch_no is not None:
        linked = select(DeviationLink.deviation_no).where(DeviationLink.batch_no == batch_no)
        query = query.where(Deviation.deviation_no.in_(linked))
    return [_with_links(session, d) for d in session.scalars(query)]


@app.get("/deviations/{deviation_no}", tags=["read"])
def deviation(deviation_no: str, session: SessionDep) -> dict[str, Any]:
    found = session.get(Deviation, deviation_no)
    if found is None:
        raise HTTPException(status_code=404, detail=f"unknown deviation {deviation_no}")
    return _with_links(session, found)


def _change_with_links(session: Session, change: ChangeControl) -> dict[str, Any]:
    links = [row_dict(link) for link in change_links_of(session, change.cc_no)]
    return {**row_dict(change), "links": links}


@app.get("/change-controls", tags=["read"])
def change_controls(session: SessionDep, batch_no: str | None = None) -> list[dict[str, Any]]:
    query = select(ChangeControl).order_by(ChangeControl.cc_no)
    if batch_no is not None:
        linked = select(ChangeControlLink.cc_no).where(ChangeControlLink.batch_no == batch_no)
        query = query.where(ChangeControl.cc_no.in_(linked))
    return [_change_with_links(session, c) for c in session.scalars(query)]


@app.get("/change-controls/{cc_no}", tags=["read"])
def change_control(cc_no: str, session: SessionDep) -> dict[str, Any]:
    found = session.get(ChangeControl, cc_no)
    if found is None:
        raise HTTPException(status_code=404, detail=f"unknown change control {cc_no}")
    return _change_with_links(session, found)


writes = APIRouter(prefix="/events", tags=["scenario events"], dependencies=[Depends(require_scenario_token)])
add_event_routes(
    writes,
    [
        ("/deviation-opened", schemas.DeviationOpenedIn, events.deviation_opened),
        ("/deviation-closed", schemas.DeviationClosedIn, events.deviation_closed),
        ("/change-control-opened", schemas.ChangeControlOpenedIn, events.change_control_opened),
        ("/change-control-status", schemas.ChangeControlStatusIn, events.change_control_status),
    ],
    get_session,
)
app.include_router(writes)
