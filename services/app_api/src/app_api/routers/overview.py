"""``GET /api/overview`` (F09-FR-02, FR-03, FR-07)."""

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from r2r_core.profile import SiteProfile
from sqlalchemy.orm import Session

from app_api.auth import current_user
from app_api.db import get_session
from app_api.deps import get_profile
from app_api.services.overview import FLAG_NAMES, Filters, InvalidFilter, OverviewOut, build_overview
from app_api.services.store import load_composed

router = APIRouter(dependencies=[Depends(current_user)])


def overview_filters(
    types: Annotated[list[str] | None, Query(alias="type[]")] = None,
    classes: Annotated[list[str] | None, Query(alias="class[]")] = None,
    campaigns: Annotated[list[str] | None, Query(alias="campaign[]")] = None,
    flags: Annotated[list[str] | None, Query(alias="flags[]")] = None,
    stage: str | None = None,
    period: str = "all",
    date_from: Annotated[dt.date | None, Query(alias="from")] = None,
    date_to: Annotated[dt.date | None, Query(alias="to")] = None,
    q: str | None = None,
) -> Filters:
    unknown = [name for name in flags or [] if name not in FLAG_NAMES]
    if unknown:
        raise HTTPException(status_code=422, detail=f"unknown flags: {', '.join(unknown)}")
    return Filters(
        types=types or (),
        classes=classes or (),
        campaigns=campaigns or (),
        stage=stage or None,
        flags=flags or (),
        period=period,
        date_from=date_from,
        date_to=date_to,
        q=q or None,
    )


@router.get("/overview")
def overview(
    filters: Annotated[Filters, Depends(overview_filters)],
    session: Annotated[Session, Depends(get_session, scope="function")],
    profile: Annotated[SiteProfile, Depends(get_profile)],
) -> OverviewOut:
    composed = load_composed(session, profile)
    try:
        return build_overview(composed.rows, filters, profile, composed.today, composed.freshness)
    except InvalidFilter as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
