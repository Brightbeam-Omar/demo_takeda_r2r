"""``GET /api/metrics``: the weekly metrics the pipeline published (F09 endpoint table, F09-FR-07).

Only ``computed_in: pipeline`` metrics have weeks; the others come back ``awaiting_signal`` with their
``null_reason``. Tier 1 does not filter the metrics (``filtered`` is false).
"""

import datetime as dt
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from r2r_core import clock
from r2r_core.profile import SiteProfile
from sqlalchemy import text
from sqlalchemy.orm import Session

from app_api.auth import current_user
from app_api.db import get_session
from app_api.deps import get_profile
from app_api.schemas import Freshness
from app_api.services.store import freshness

router = APIRouter(dependencies=[Depends(current_user)])


class WeekOut(BaseModel):
    week_start: dt.date
    completed: int
    on_time: int
    pct: Decimal | None
    rag: str | None


class MetricOut(BaseModel):
    metric_id: str
    label: str
    stage_key: str | None
    sla_days: int | None
    computed_in: str
    status: str
    null_reason: str | None
    weeks: list[WeekOut]


class MetricsOut(BaseModel):
    freshness: Freshness
    filtered: bool
    week_starts: list[dt.date]
    metrics: list[MetricOut]


def metric_rag(pct: Decimal | None, profile: SiteProfile) -> str | None:
    if pct is None:
        return None
    if pct >= profile.metric_rag.green_min_pct:
        return "green"
    return "amber" if pct >= profile.metric_rag.amber_min_pct else "red"


@router.get("/metrics")
def metrics(
    session: Annotated[Session, Depends(get_session, scope="function")],
    profile: Annotated[SiteProfile, Depends(get_profile)],
) -> MetricsOut:
    weeks: dict[str, list[WeekOut]] = {}
    for row in session.execute(
        text(
            "SELECT metric_id, week_start, completed, on_time, pct FROM mirror_weekly_metrics "
            "ORDER BY week_start"
        )
    ):
        weeks.setdefault(row.metric_id, []).append(
            WeekOut(
                week_start=row.week_start,
                completed=row.completed,
                on_time=row.on_time,
                pct=row.pct,
                rag=metric_rag(row.pct, profile),
            )
        )
    reference = session.execute(text("SELECT * FROM mirror_metric_reference ORDER BY metric_id")).mappings()
    return MetricsOut(
        freshness=freshness(session, clock.now()),
        filtered=False,
        week_starts=sorted({week.week_start for series in weeks.values() for week in series}),
        metrics=[
            MetricOut(**{k: v for k, v in ref.items()}, weeks=weeks.get(ref["metric_id"], []))
            for ref in reference
        ],
    )
