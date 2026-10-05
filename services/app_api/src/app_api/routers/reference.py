"""``GET /api/reference``: the lists the filters and forms are built from (F09 endpoint table)."""

import os
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from r2r_core.profile import SiteProfile
from sqlalchemy import text
from sqlalchemy.orm import Session

from app_api.auth import current_user
from app_api.db import get_session
from app_api.deps import get_profile
from app_api.services.overview import FLAG_NAMES, PERIODS

DEFAULT_RELEASE_BADGE = "ALPHA – LOCAL"

router = APIRouter(dependencies=[Depends(current_user)])


class ReferenceOut(BaseModel):
    site_name: str
    site_timezone: str
    stages: list[dict[str, Any]]
    metrics: list[dict[str, Any]]
    reason_codes: list[dict[str, Any]]
    molecule_types: list[dict[str, str]]
    classes: list[dict[str, str]]
    campaigns: list[str]
    flags: list[str]
    periods: list[str]
    metric_rag: dict[str, int]
    terms: dict[str, str]
    release_badge: str
    air_gap_threshold_hours: int


def _rows(session: Session, sql: str) -> list[dict[str, Any]]:
    return [dict(row) for row in session.execute(text(sql)).mappings()]


@router.get("/reference")
def reference(
    session: Annotated[Session, Depends(get_session, scope="function")],
    profile: Annotated[SiteProfile, Depends(get_profile)],
) -> ReferenceOut:
    campaigns = session.scalars(
        text("SELECT DISTINCT campaign FROM mirror_batch_pipeline WHERE campaign IS NOT NULL ORDER BY 1")
    )
    return ReferenceOut(
        site_name=profile.site.name,
        site_timezone=profile.site.timezone,
        stages=_rows(session, "SELECT * FROM mirror_stage_reference ORDER BY sort"),
        metrics=_rows(session, "SELECT * FROM mirror_metric_reference ORDER BY metric_id"),
        reason_codes=_rows(session, "SELECT code, label FROM mirror_reason_codes ORDER BY code"),
        molecule_types=[item.model_dump() for item in profile.molecule_types],
        classes=[item.model_dump() for item in profile.material_classes],
        campaigns=list(campaigns),
        flags=list(FLAG_NAMES),
        periods=list(PERIODS),
        metric_rag={
            "green_min_pct": profile.metric_rag.green_min_pct,
            "amber_min_pct": profile.metric_rag.amber_min_pct,
        },
        terms=profile.terms.model_dump(),
        air_gap_threshold_hours=profile.air_gap.threshold_hours,
        release_badge=os.environ.get("RELEASE_BADGE", "").strip() or DEFAULT_RELEASE_BADGE,
    )
