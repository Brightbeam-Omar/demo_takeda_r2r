"""``GET /api/teams``: the Team Dashboard (F21-FR-06, OQ-133).

A snapshot of the open work per owning team, from the stage reference. It ignores every filter and the
period: it answers "who has what, and how late is it" for the whole site. Late and amber come from the same
composed plan as the Overview, so the late counts add up to the Overview's late count.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from r2r_core.profile import SiteProfile
from sqlalchemy import text
from sqlalchemy.orm import Session

from app_api.auth import current_user
from app_api.db import get_session
from app_api.deps import get_profile
from app_api.services.store import load_composed

router = APIRouter(dependencies=[Depends(current_user)])


class TeamOut(BaseModel):
    team: str
    stage_keys: list[str]
    stage_labels: list[str]
    open: int
    late: int
    oldest_late_days: int | None  # days over the plan for the team's most overdue lot
    amber: int
    at_risk_pct: float | None  # amber lots as a share of the open lots, None without open lots


class TeamTotals(BaseModel):
    open: int
    late: int
    amber: int


class TeamsOut(BaseModel):
    teams: list[TeamOut]
    totals: TeamTotals


@router.get("/teams")
def teams(
    session: Annotated[Session, Depends(get_session, scope="function")],
    profile: Annotated[SiteProfile, Depends(get_profile)],
) -> TeamsOut:
    reference = session.execute(
        text("SELECT stage_key, label, team, terminal FROM mirror_stage_reference ORDER BY sort")
    ).mappings()
    owned: dict[str, list[tuple[str, str]]] = {}
    for stage in reference:
        if not stage["terminal"]:  # the terminal stage is an outcome, not a team's work
            owned.setdefault(stage["team"], []).append((stage["stage_key"], stage["label"]))
    team_of = {key: team for team, stages in owned.items() for key, _ in stages}

    open_rows: dict[str, int] = dict.fromkeys(owned, 0)
    late: dict[str, int] = dict.fromkeys(owned, 0)
    amber: dict[str, int] = dict.fromkeys(owned, 0)
    over: dict[str, int] = {}
    for row in load_composed(session, profile).rows:
        team = team_of.get(str(row.facts["stage_key"]))
        # A lot that has not entered a stage yet (pending) has no owner's work to do (03 section 4).
        if team is None or row.stage_terminal or row.facts["current_stage_entry_date"] is None:
            continue
        open_rows[team] += 1
        if row.plan.late:
            late[team] += 1
            days_over = -(row.plan.days_remaining or 0)
            over[team] = max(over.get(team, 0), days_over)
        elif row.plan.rag == "amber":
            amber[team] += 1
    result = [
        TeamOut(
            team=team,
            stage_keys=[key for key, _ in stages],
            stage_labels=[label for _, label in stages],
            open=open_rows[team],
            late=late[team],
            oldest_late_days=over.get(team),
            amber=amber[team],
            at_risk_pct=round(100 * amber[team] / open_rows[team], 1) if open_rows[team] else None,
        )
        for team, stages in owned.items()
    ]
    return TeamsOut(
        teams=result,
        totals=TeamTotals(
            open=sum(t.open for t in result),
            late=sum(t.late for t in result),
            amber=sum(t.amber for t in result),
        ),
    )
