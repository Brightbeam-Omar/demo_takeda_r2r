"""``GET /api/overview`` (F09-FR-02, FR-03, FR-07)."""

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from r2r_core.profile import SiteProfile
from sqlalchemy import select as sql_select
from sqlalchemy import text
from sqlalchemy.orm import Session

from app_api.auth import current_user
from app_api.db import get_session
from app_api.deps import get_profile
from app_api.models import AppUser
from app_api.services.bookmarks import bookmarked_keys
from app_api.services.overview import FLAG_NAMES, Filters, InvalidFilter, OverviewOut, build_overview, select
from app_api.services.store import load_composed
from app_api.services.windows import AdjustedOut, InsightsOut, build_adjusted, build_insights

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
    bookmarked: bool = False,
    *,
    session: Annotated[Session, Depends(get_session, scope="function")],
    user: Annotated[AppUser, Depends(current_user)],
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
        bookmarked_keys=frozenset(bookmarked_keys(session, user.user_key)) if bookmarked else None,
    )


@router.get("/overview")
def overview(
    filters: Annotated[Filters, Depends(overview_filters)],
    session: Annotated[Session, Depends(get_session, scope="function")],
    profile: Annotated[SiteProfile, Depends(get_profile)],
    user: Annotated[AppUser, Depends(current_user)],
) -> OverviewOut:
    composed = load_composed(session, profile)
    try:
        return build_overview(
            composed.rows,
            filters,
            profile,
            composed.today,
            composed.freshness,
            bookmarks=bookmarked_keys(session, user.user_key),
        )
    except InvalidFilter as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/overview/adjusted")
def adjusted(
    filters: Annotated[Filters, Depends(overview_filters)],
    session: Annotated[Session, Depends(get_session, scope="function")],
    profile: Annotated[SiteProfile, Depends(get_profile)],
) -> AdjustedOut:
    """The Adjusted Needs-by Dates window (F16-FR-07): every filter except stage applies."""
    composed = load_composed(session, profile)
    try:
        rows = select(composed.rows, filters, composed.today, with_stage=False)
    except InvalidFilter as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    labels = {
        code: label
        for code, label in session.execute(text("SELECT code, label FROM mirror_reason_codes")).tuples()
    }
    names = {
        key: name
        for key, name in session.execute(sql_select(AppUser.user_key, AppUser.display_name)).tuples()
    }
    return build_adjusted(rows, labels, names)


@router.get("/overview/insights")
def insights(
    filters: Annotated[Filters, Depends(overview_filters)],
    session: Annotated[Session, Depends(get_session, scope="function")],
    profile: Annotated[SiteProfile, Depends(get_profile)],
) -> InsightsOut:
    """The air-gap insights window (F16-FR-09): every air-gap row, worst first, no cap."""
    composed = load_composed(session, profile)
    try:
        rows = select(composed.rows, filters, composed.today, with_stage=False)
    except InvalidFilter as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return build_insights(rows, {stage.key: stage.label for stage in profile.stages})
