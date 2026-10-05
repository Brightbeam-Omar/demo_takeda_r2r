"""``POST/GET /api/feedback``: the floating Feedback button and the admin list (F15-FR-06, OQ-083).

Any persona may post, including the viewer. Feedback is not a business change, so it is not audited. The
list is admin only, newest first.
"""

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator
from r2r_core import clock
from sqlalchemy import select
from sqlalchemy.orm import Session

from app_api.auth import current_user, require_role
from app_api.db import get_session
from app_api.models import AppUser, Feedback

router = APIRouter()


class FeedbackIn(BaseModel):
    page: Annotated[str, Field(max_length=200)]
    message: Annotated[str, Field(min_length=1, max_length=2000)]

    @field_validator("message")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message must not be blank")
        return value


class FeedbackOut(BaseModel):
    id: int
    at: dt.datetime
    user_key: str
    page: str
    message: str


@router.post("/feedback", status_code=201)
def post_feedback(
    body: FeedbackIn,
    session: Annotated[Session, Depends(get_session, scope="function")],
    user: Annotated[AppUser, Depends(current_user)],
) -> FeedbackOut:
    entry = Feedback(at=clock.now(), user_key=user.user_key, page=body.page, message=body.message)
    session.add(entry)
    session.commit()
    return FeedbackOut.model_validate(entry, from_attributes=True)


@router.get("/feedback", dependencies=[Depends(require_role("admin"))])
def list_feedback(session: Annotated[Session, Depends(get_session, scope="function")]) -> list[FeedbackOut]:
    entries = session.scalars(select(Feedback).order_by(Feedback.id.desc()))
    return [FeedbackOut.model_validate(entry, from_attributes=True) for entry in entries]
