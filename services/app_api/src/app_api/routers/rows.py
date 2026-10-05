"""Row detail, the explain endpoints and human input on one row (F09-FR-04, FR-06)."""

import datetime as dt
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from r2r_core.profile import SiteProfile
from sqlalchemy.orm import Session

from app_api.auth import require_role
from app_api.db import get_session
from app_api.deps import get_profile
from app_api.models import AppUser
from app_api.schemas import RowOut
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


class CommentOut(BaseModel):
    id: int
    row_key: str
    body: str
    author_user_key: str
    created_at: dt.datetime


def recomputed(session: Session, profile: SiteProfile, row_key: str) -> RowOut:
    composed = load_composed(session, profile)
    labels = {stage.key: stage.label for stage in profile.stages}
    for row in composed.rows:
        if row.row_key == row_key:
            return RowOut.of(row, labels)
    raise HTTPException(status_code=404, detail=f"unknown row {row_key}")


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
