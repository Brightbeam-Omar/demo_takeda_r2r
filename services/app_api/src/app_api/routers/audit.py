"""``GET /api/audit``: audit events, newest first, filtered and paginated (F09 endpoint table, OQ-062)."""

import datetime as dt
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from r2r_core.profile import SiteProfile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app_api.auth import current_user
from app_api.db import get_session
from app_api.deps import get_profile
from app_api.models import AuditEvent

router = APIRouter(dependencies=[Depends(current_user)])


class AuditOut(BaseModel):
    id: int
    at: dt.datetime
    actor_user_key: str | None
    action: str
    row_key: str | None
    details: Any


class AuditPage(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[AuditOut]


@router.get("/audit")
def audit(
    session: Annotated[Session, Depends(get_session, scope="function")],
    profile: Annotated[SiteProfile, Depends(get_profile)],
    row_key: str | None = None,
    actor: str | None = None,
    action: str | None = None,
    date_from: Annotated[dt.date | None, Query(alias="from")] = None,
    date_to: Annotated[dt.date | None, Query(alias="to")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AuditPage:
    conditions = []
    if row_key:
        conditions.append(AuditEvent.row_key == row_key)
    if actor:
        conditions.append(AuditEvent.actor_user_key == actor)
    if action:
        conditions.append(AuditEvent.action == action)
    # `from` and `to` are demo-clock dates in the site timezone, both inclusive (F11, OQ-068).
    if date_from and date_to and date_to < date_from:
        raise HTTPException(status_code=422, detail="'to' is before 'from'")
    if date_from:
        conditions.append(
            AuditEvent.at >= dt.datetime.combine(date_from, dt.time.min, tzinfo=profile.site.tz)
        )
    if date_to:
        end = dt.datetime.combine(date_to + dt.timedelta(days=1), dt.time.min, tzinfo=profile.site.tz)
        conditions.append(AuditEvent.at < end)
    total = session.scalar(select(func.count()).select_from(AuditEvent).where(*conditions)) or 0
    events = session.scalars(
        select(AuditEvent).where(*conditions).order_by(AuditEvent.id.desc()).limit(limit).offset(offset)
    )
    return AuditPage(
        total=total,
        limit=limit,
        offset=offset,
        items=[
            AuditOut(
                id=e.id,
                at=e.at,
                actor_user_key=e.actor_user_key,
                action=e.action,
                row_key=e.row_key,
                details=e.details_json,
            )
            for e in events
        ],
    )
