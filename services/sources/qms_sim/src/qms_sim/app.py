"""QMS simulator API (port 8103): open reads, token-guarded scenario writes."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from r2r_core.db import row_dict
from r2r_core.web import add_event_routes, health_router, install_error_handlers, require_scenario_token
from sqlalchemy import select
from sqlalchemy.orm import Session

from qms_sim import events, schemas
from qms_sim.db import get_session
from qms_sim.events import links_of
from qms_sim.models import Deviation, DeviationLink

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


writes = APIRouter(prefix="/events", tags=["scenario events"], dependencies=[Depends(require_scenario_token)])
add_event_routes(
    writes,
    [
        ("/deviation-opened", schemas.DeviationOpenedIn, events.deviation_opened),
        ("/deviation-closed", schemas.DeviationClosedIn, events.deviation_closed),
    ],
    get_session,
)
app.include_router(writes)
