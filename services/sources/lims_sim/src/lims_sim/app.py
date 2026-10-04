"""LIMS simulator API (port 8102): open reads, token-guarded scenario writes."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from r2r_core.db import row_dict
from r2r_core.web import add_event_routes, health_router, install_error_handlers, require_scenario_token
from sqlalchemy import select
from sqlalchemy.orm import Session

from lims_sim import events, schemas
from lims_sim.db import get_session
from lims_sim.models import Sample, TestResult

SessionDep = Annotated[Session, Depends(get_session)]

app = FastAPI(
    title="LIMS simulator",
    description="LIMS stand-in. `/events/*` are scenario writes (`X-Scenario-Token`).",
)
install_error_handlers(app)
app.include_router(health_router("lims-sim"))


@app.get("/samples", tags=["read"])
def samples(
    session: SessionDep, batch_no: str | None = None, material_no: str | None = None
) -> list[dict[str, Any]]:
    query = select(Sample).order_by(Sample.sample_id)
    if batch_no is not None:
        query = query.where(Sample.batch_no == batch_no)
    if material_no is not None:
        query = query.where(Sample.material_no == material_no)
    return [row_dict(s) for s in session.scalars(query)]


def _known_sample(session: Session, sample_id: str) -> Sample:
    found = session.get(Sample, sample_id)
    if found is None:
        raise HTTPException(status_code=404, detail=f"unknown sample {sample_id}")
    return found


@app.get("/samples/{sample_id}", tags=["read"])
def sample(sample_id: str, session: SessionDep) -> dict[str, Any]:
    return row_dict(_known_sample(session, sample_id))


@app.get("/samples/{sample_id}/results", tags=["read"])
def results(sample_id: str, session: SessionDep) -> list[dict[str, Any]]:
    _known_sample(session, sample_id)
    query = select(TestResult).where(TestResult.sample_id == sample_id).order_by(TestResult.id)
    return [row_dict(r) for r in session.scalars(query)]


writes = APIRouter(prefix="/events", tags=["scenario events"], dependencies=[Depends(require_scenario_token)])
add_event_routes(
    writes,
    [
        ("/sample-collected", schemas.SampleCollectedIn, events.sample_collected),
        ("/sample-shipped", schemas.SampleShippedIn, events.sample_shipped),
        ("/testing-started", schemas.SampleRef, events.testing_started),
        ("/approved", schemas.SampleRef, events.approved),
        ("/rejected", schemas.SampleRef, events.rejected),
        ("/test-result", schemas.TestResultIn, events.test_result_recorded),
    ],
    get_session,
)
app.include_router(writes)
