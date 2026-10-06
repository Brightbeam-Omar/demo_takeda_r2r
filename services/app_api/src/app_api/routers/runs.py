"""``GET /api/pipeline/runs``: the run history behind the Sync Status page (F21-FR-02).

Served from ``mirror_pipeline_runs`` and ``mirror_pipeline_run_steps``. A run's ``started_at`` is demo-clock
time, so its age is measured against the demo clock (OQ-135); the sync-event ages stay wall-clock.
"""

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from r2r_core import clock
from sqlalchemy import text
from sqlalchemy.orm import Session

from app_api.auth import current_user
from app_api.db import get_session

router = APIRouter(dependencies=[Depends(current_user)])


class PipelineRunOut(BaseModel):
    pipeline_run_id: str
    started_at: dt.datetime | None
    age_seconds: int | None
    duration_ms: int | None
    files: int | None
    inserted: int | None
    total: int | None
    skipped: int | None
    status: str
    failed_step: str | None


class PipelineStepOut(BaseModel):
    step: str
    status: str
    started_at: dt.datetime | None
    finished_at: dt.datetime | None
    duration_ms: int | None
    rows: int | None
    error: str | None


class PipelineStepsOut(BaseModel):
    pipeline_run_id: str
    steps: list[PipelineStepOut]


@router.get("/pipeline/runs")
def pipeline_runs(
    session: Annotated[Session, Depends(get_session, scope="function")],
) -> list[PipelineRunOut]:
    now = clock.now()
    rows = session.execute(
        text(
            "SELECT pipeline_run_id, started_at, duration_ms, files, inserted, total, skipped, status, "
            "failed_step FROM mirror_pipeline_runs ORDER BY run_seq DESC, pipeline_run_id DESC"
        )
    ).mappings()
    return [
        PipelineRunOut(
            **row,
            age_seconds=None
            if row["started_at"] is None
            else max(0, int((now - row["started_at"]).total_seconds())),
        )
        for row in rows
    ]


@router.get("/pipeline/runs/{pipeline_run_id}/steps")
def pipeline_run_steps(
    pipeline_run_id: str, session: Annotated[Session, Depends(get_session, scope="function")]
) -> PipelineStepsOut:
    rows = (
        session.execute(
            text(
                "SELECT step, status, started_at, finished_at, duration_ms, rows, error "
                "FROM mirror_pipeline_run_steps "
                "WHERE pipeline_run_id = :run "
                "ORDER BY array_position("
                "ARRAY['setup','extract','transform','snapshot_aggregate','publish','notify'], step)"
            ),
            {"run": pipeline_run_id},
        )
        .mappings()
        .all()
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"no steps recorded for run {pipeline_run_id}")
    return PipelineStepsOut(pipeline_run_id=pipeline_run_id, steps=[PipelineStepOut(**row) for row in rows])
