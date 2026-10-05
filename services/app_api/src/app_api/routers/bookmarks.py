"""``/api/bookmarks``: a user's personal stars on rows (F16-FR-04, OQ-091).

Any persona, including the viewer, may bookmark. A bookmark is personal, not a business change, so it is not
written to ``audit_event``.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from r2r_core import clock
from r2r_core.profile import SiteProfile
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app_api.auth import current_user
from app_api.db import get_session
from app_api.deps import get_profile
from app_api.models import AppUser, Bookmark
from app_api.services.bookmarks import bookmarked_keys
from app_api.services.store import load_composed

router = APIRouter()


@router.get("/bookmarks")
def list_bookmarks(
    session: Annotated[Session, Depends(get_session, scope="function")],
    user: Annotated[AppUser, Depends(current_user)],
) -> list[str]:
    return bookmarked_keys(session, user.user_key)


@router.post("/bookmarks/{row_key}", status_code=201)
def add_bookmark(
    row_key: str,
    session: Annotated[Session, Depends(get_session, scope="function")],
    user: Annotated[AppUser, Depends(current_user)],
    profile: Annotated[SiteProfile, Depends(get_profile)],
) -> dict[str, str]:
    if not any(row.row_key == row_key for row in load_composed(session, profile).rows):
        raise HTTPException(status_code=404, detail=f"unknown row {row_key}")
    if session.get(Bookmark, (user.user_key, row_key)) is None:
        session.add(Bookmark(user_key=user.user_key, row_key=row_key, created_at=clock.now()))
    return {"row_key": row_key}


@router.delete("/bookmarks/{row_key}", status_code=204)
def remove_bookmark(
    row_key: str,
    session: Annotated[Session, Depends(get_session, scope="function")],
    user: Annotated[AppUser, Depends(current_user)],
) -> Response:
    session.execute(delete(Bookmark).where(Bookmark.user_key == user.user_key, Bookmark.row_key == row_key))
    return Response(status_code=204)
