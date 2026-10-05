"""Row detail, the explain endpoints and human input on one row (F09-FR-04, FR-06)."""

import datetime as dt
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from r2r_core.profile import SiteProfile
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app_api.auth import current_user, require_role
from app_api.db import get_session
from app_api.deps import get_profile
from app_api.models import AppUser, Comment, OverrideValue
from app_api.schemas import CommentOut, DeviationOut, OverrideOut, RowDetail, RowOut
from app_api.services import overrides
from app_api.services.store import load_composed

router = APIRouter()

PLANNERS = ("planner", "admin")
STATUS_SETTERS = ("qc_lead", "qa_release", "admin")
COMMENTERS = ("planner", "qc_lead", "qa_release", "admin")


class NeedByIn(BaseModel):
    adjusted_date: dt.date | None = None
    reason_code: str | None = None
    expedite: bool = False
    note: str | None = None


class StatusIn(BaseModel):
    rag: Literal["red", "amber", "green"] | None = None
    reason: str | None = None
    team: str | None = None


class CommentIn(BaseModel):
    body: str


def recomputed(session: Session, profile: SiteProfile, row_key: str) -> RowOut:
    composed = load_composed(session, profile)
    labels = {stage.key: stage.label for stage in profile.stages}
    for row in composed.rows:
        if row.row_key == row_key:
            return RowOut.of(row, labels)
    raise HTTPException(status_code=404, detail=f"unknown row {row_key}")


def _override_out(entry: OverrideValue) -> OverrideOut:
    return OverrideOut(
        id=entry.id,
        field=entry.field,
        value=entry.value_json,
        reason_code=entry.reason_code,
        note=entry.note,
        version=entry.version,
        author_user_key=entry.author_user_key,
        created_at=entry.created_at,
        is_current=entry.is_current,
    )


@router.get("/rows/{row_key}", dependencies=[Depends(current_user)])
def get_row(
    row_key: str,
    session: Annotated[Session, Depends(get_session)],
    profile: Annotated[SiteProfile, Depends(get_profile)],
) -> RowDetail:
    composed = load_composed(session, profile)
    labels = {stage.key: stage.label for stage in profile.stages}
    found = next((row for row in composed.rows if row.row_key == row_key), None)
    if found is None:
        raise HTTPException(status_code=404, detail=f"unknown row {row_key}")
    history = list(
        session.scalars(
            select(OverrideValue).where(OverrideValue.row_key == row_key).order_by(OverrideValue.id.desc())
        )
    )
    comments = session.scalars(select(Comment).where(Comment.row_key == row_key).order_by(Comment.id.desc()))
    batch_key = (found.facts["material_no"], found.facts["batch_no"])
    deviations = session.execute(
        text(
            "SELECT deviation_no, title, severity, status, opened_on, closed_on, root_cause_category, owner "
            "FROM mirror_deviations WHERE material_no = :m AND batch_no = :b ORDER BY deviation_no"
        ),
        {"m": batch_key[0], "b": batch_key[1]},
    ).mappings()
    siblings = [
        RowOut.of(row, labels)
        for row in composed.rows
        if (row.facts["material_no"], row.facts["batch_no"]) == batch_key and row.row_key != row_key
    ]
    return RowDetail(
        **RowOut.of(found, labels).model_dump(),
        freshness=composed.freshness,
        facts=dict(found.facts),
        current_overrides={o.field: _override_out(o) for o in history if o.is_current},
        override_history=[_override_out(o) for o in history],
        comments=[CommentOut.model_validate(c, from_attributes=True) for c in comments],
        deviations=[DeviationOut(**d) for d in deviations],
        siblings=siblings,
    )


@router.put("/rows/{row_key}/need-by")
def put_need_by(
    row_key: str,
    body: NeedByIn,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[AppUser, Depends(require_role(*PLANNERS))],
    profile: Annotated[SiteProfile, Depends(get_profile)],
) -> RowOut:
    overrides.set_need_by(
        session, user, row_key, body.adjusted_date, body.reason_code, body.expedite, body.note
    )
    return recomputed(session, profile, row_key)


@router.put("/rows/{row_key}/status")
def put_status(
    row_key: str,
    body: StatusIn,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[AppUser, Depends(require_role(*STATUS_SETTERS))],
    profile: Annotated[SiteProfile, Depends(get_profile)],
) -> RowOut:
    overrides.set_status(session, user, row_key, body.rag, body.reason, body.team)
    return recomputed(session, profile, row_key)


@router.post("/rows/{row_key}/comments", status_code=201)
def post_comment(
    row_key: str,
    body: CommentIn,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[AppUser, Depends(require_role(*COMMENTERS))],
) -> CommentOut:
    comment = overrides.add_comment(session, user, row_key, body.body)
    return CommentOut(
        id=comment.id,
        row_key=comment.row_key,
        body=comment.body,
        author_user_key=comment.author_user_key,
        created_at=comment.created_at,
    )
