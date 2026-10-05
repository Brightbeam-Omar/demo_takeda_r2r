"""``GET /api/me``, ``/api/users`` and ``/api/clock`` (F09-FR-05)."""

import os
from datetime import date, datetime
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from r2r_core import clock
from r2r_core.profile import SiteProfile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app_api.auth import current_user, demo_mode
from app_api.db import get_session
from app_api.deps import get_profile
from app_api.models import AppUser

router = APIRouter()


class UserOut(BaseModel):
    user_key: str
    display_name: str
    role: str


class ClockOut(BaseModel):
    now_utc: datetime
    today_local: date
    frozen: bool


@router.get("/me")
def me(user: Annotated[AppUser, Depends(current_user)]) -> UserOut:
    return UserOut(user_key=user.user_key, display_name=user.display_name, role=user.role)


@router.get("/users")
def users(session: Annotated[Session, Depends(get_session, scope="function")]) -> list[UserOut]:
    """The personas for the switcher. It needs no identity (the switcher runs before one is chosen)."""
    if not demo_mode():
        raise HTTPException(status_code=404, detail="personas exist only in demo mode")
    rows = session.scalars(select(AppUser).order_by(AppUser.user_key))
    return [UserOut(user_key=u.user_key, display_name=u.display_name, role=u.role) for u in rows]


@router.get("/clock")
def demo_clock(profile: Annotated[SiteProfile, Depends(get_profile)]) -> ClockOut:
    """The scenario service's clock; if it is down, the same clock read from the app database."""
    url = os.environ.get("SCENARIO_URL", "http://scenario:8100").rstrip("/")
    try:
        response = httpx.get(f"{url}/clock", timeout=0.5)
        response.raise_for_status()
        return ClockOut.model_validate(response.json())
    except (httpx.HTTPError, ValueError, KeyError):
        now = clock.now()
        return ClockOut(now_utc=now, today_local=now.astimezone(profile.site.tz).date(), frozen=False)
