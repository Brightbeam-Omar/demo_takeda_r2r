"""The explain endpoints (F09-FR-06)."""

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from r2r_core.profile import SiteProfile
from r2r_core.stage_rules import RULES
from sqlalchemy import text
from sqlalchemy.orm import Session

from app_api.auth import current_user
from app_api.db import get_session
from app_api.deps import get_profile
from app_api.routers.overview import overview_filters
from app_api.schemas import Freshness
from app_api.services.explain import (
    CompletionExplain,
    FlowExplain,
    MetricExplain,
    MetricRowOut,
    RuleOut,
    StageExplain,
    explain_completion,
    explain_stage,
)
from app_api.services.overview import Filters, InvalidFilter, select
from app_api.services.store import Composed, load_composed

router = APIRouter(dependencies=[Depends(current_user)])


@router.get("/rows/{row_key}/explain")
def explain_row(
    row_key: str,
    field: Annotated[str, Query(pattern="^(stage|expected_completion)$")],
    session: Annotated[Session, Depends(get_session, scope="function")],
    profile: Annotated[SiteProfile, Depends(get_profile)],
) -> StageExplain | CompletionExplain:
    composed = load_composed(session, profile)
    row = next((r for r in composed.rows if r.row_key == row_key), None)
    if row is None:
        raise HTTPException(status_code=404, detail=f"unknown row {row_key}")
    if field == "stage":
        return explain_stage(row, profile, composed.freshness)
    return explain_completion(row, profile, composed.freshness)


@router.get("/explain")
def explain_figure(
    field: str,
    filters: Annotated[Filters, Depends(overview_filters)],
    session: Annotated[Session, Depends(get_session, scope="function")],
    profile: Annotated[SiteProfile, Depends(get_profile)],
    week: dt.date | None = None,
) -> MetricExplain | FlowExplain:
    composed = load_composed(session, profile)
    kind, _, name = field.partition(":")
    if kind == "metric":
        return _metric(session, composed.freshness, name, week or _this_monday(composed.today))
    if kind == "flow":
        return _flow(composed, profile, filters, name)
    raise HTTPException(status_code=422, detail="field must be metric:<id> or flow:<stage_key>")


def _this_monday(today: dt.date) -> dt.date:
    return today - dt.timedelta(days=today.weekday())


def _metric(session: Session, fresh: Freshness, metric_id: str, week: dt.date) -> MetricExplain:
    reference = session.execute(
        text("SELECT * FROM mirror_metric_reference WHERE metric_id = :m"), {"m": metric_id}
    ).mappings().first()  # fmt: skip
    if reference is None:
        raise HTTPException(status_code=404, detail=f"unknown metric {metric_id}")
    common = {
        "metric_id": metric_id,
        "label": reference["label"],
        "status": reference["status"],
        "null_reason": reference["null_reason"],
        "sla_days": reference["sla_days"],
        "freshness": fresh,
    }
    if reference["status"] != "active":
        return MetricExplain(
            **common, week_start=None, completed=None, on_time=None, pct=None, rows=[]
        )  # fmt: skip
    figure = session.execute(
        text(
            "SELECT completed, on_time, pct FROM mirror_weekly_metrics "
            "WHERE metric_id = :m AND week_start = :w"
        ),
        {"m": metric_id, "w": week},
    ).first()
    if figure is None:
        raise HTTPException(status_code=404, detail=f"week {week} is not published for {metric_id}")
    rows = session.execute(
        text(
            "SELECT row_key, entry_date, exit_date, duration_days, sla_days, on_time "
            "FROM mirror_weekly_metric_rows WHERE metric_id = :m AND week_start = :w ORDER BY row_key"
        ),
        {"m": metric_id, "w": week},
    ).mappings()
    return MetricExplain(
        **common,
        week_start=week,
        completed=figure.completed,
        on_time=figure.on_time,
        pct=figure.pct,
        rows=[MetricRowOut(**r) for r in rows],
    )


def _flow(composed: Composed, profile: SiteProfile, filters: Filters, stage_key: str) -> FlowExplain:
    stages = {s.key: s for s in profile.stages}
    if stage_key not in stages:
        raise HTTPException(status_code=404, detail=f"unknown stage {stage_key}")
    try:
        rows = [
            r for r in select(composed.rows, filters, composed.today, with_stage=False)
            if r.facts["stage_key"] == stage_key
        ]  # fmt: skip
    except InvalidFilter as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    shown = {
        "type": list(filters.types), "class": list(filters.classes), "campaign": list(filters.campaigns),
        "flags": list(filters.flags), "period": filters.period, "from": filters.date_from,
        "to": filters.date_to, "q": filters.q,
    }  # fmt: skip
    return FlowExplain(
        stage_key=stage_key,
        stage_label=stages[stage_key].label,
        count=len(rows),
        breached=any(r.plan.late for r in rows),
        mode="snapshot" if filters.period == "all" else "due_in_period",
        filters=shown,
        rules=[RuleOut.of(rule) for rule in RULES if rule.stage_key == stage_key],
        row_keys=[r.row_key for r in rows],
        freshness=composed.freshness,
    )
