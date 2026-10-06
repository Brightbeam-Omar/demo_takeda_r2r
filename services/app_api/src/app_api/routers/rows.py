"""Row detail, the explain endpoints and human input on one row (F09-FR-04, FR-06)."""

import datetime as dt
import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from r2r_core.profile import SiteProfile
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app_api.auth import current_user, require_role
from app_api.db import get_session
from app_api.deps import get_profile
from app_api.models import AppUser, OverrideValue
from app_api.schemas import (
    ChangeControlOut,
    DeviationOut,
    InboundCheckOut,
    InboundItemOut,
    OverrideOut,
    PlanOut,
    RowDetail,
    RowOut,
    SampleOut,
    StatusLogOut,
)
from app_api.services import overrides, status_log
from app_api.services.compose import ADJUSTED, EXPEDITE, CurrentOverride, compose_row
from app_api.services.store import load_composed

router = APIRouter()

PLANNERS = ("planner", "admin")
LOGGERS = ("planner", "qc_lead", "qa_release", "admin")  # F19-FR-05: every role except viewer
HOLDERS = ("planner", "qa_release", "admin")  # F18-FR-08
COA_RELEASERS = ("qa_release", "admin")


class NeedByIn(BaseModel):
    adjusted_date: dt.date | None = None
    reason_code: str | None = None
    expedite: bool = False
    note: str | None = None


class PreviewOut(BaseModel):
    """The plan now and the plan as it would be after the change; nothing is stored (F11-FR-02, OQ-067)."""

    current: PlanOut
    preview: PlanOut
    system_need_by_locked: dt.date | None
    operative_need_by: dt.date | None


class StatusLogIn(BaseModel):
    status: str
    team: str | None = None
    reason_code: str | None = None
    comment: str


class StatusLogPage(BaseModel):
    count: int
    latest: StatusLogOut | None
    entries: list[StatusLogOut]


class ToggleIn(BaseModel):
    """Body of Place/Release Hold and Release on COA/Undo: the reason is required either way (OQ-103)."""

    on: bool
    reason: str


def _inbound_check(session: Session, row_key: str) -> InboundCheckOut | None:
    found = (
        session.execute(
            text(
                "SELECT prueflos, status, deadline, failed_count, items_json FROM mirror_inbound_checks "
                "WHERE row_key = :k"
            ),
            {"k": row_key},
        )
        .mappings()
        .first()
    )
    if found is None:
        return None
    return InboundCheckOut(
        prueflos=found["prueflos"],
        status=found["status"],
        deadline=found["deadline"],
        failed_count=found["failed_count"],
        items=[InboundItemOut(**item) for item in json.loads(found["items_json"] or "[]")],
    )


def _latest_of(row: object) -> dict[str, object] | None:
    """The composed row's latest status as the mapping ``compose_row`` takes again (used by the preview)."""
    latest = getattr(row, "latest_status", None)
    if latest is None:
        return None
    return {
        "status": latest.status,
        "team": latest.team,
        "reason_code": latest.reason_code,
        "comment": latest.comment,
        "author_user_key": latest.author_user_key,
        "at": latest.at,
    }


def recomputed(session: Session, profile: SiteProfile, row_key: str) -> RowOut:
    composed = load_composed(session, profile)
    labels = {stage.key: stage.label for stage in profile.stages}
    for row in composed.rows:
        if row.row_key == row_key:
            return RowOut.of(row, labels)
    raise HTTPException(status_code=404, detail=f"unknown row {row_key}")


def _override_out(entry: OverrideValue) -> OverrideOut:
    return OverrideOut(
        id=entry.id,
        field=entry.field,
        value=entry.value_json,
        reason_code=entry.reason_code,
        note=entry.note,
        version=entry.version,
        author_user_key=entry.author_user_key,
        created_at=entry.created_at,
        is_current=entry.is_current,
    )


@router.get("/rows/{row_key}", dependencies=[Depends(current_user)])
def get_row(
    row_key: str,
    session: Annotated[Session, Depends(get_session, scope="function")],
    profile: Annotated[SiteProfile, Depends(get_profile)],
) -> RowDetail:
    composed = load_composed(session, profile)
    labels = {stage.key: stage.label for stage in profile.stages}
    found = next((row for row in composed.rows if row.row_key == row_key), None)
    if found is None:
        raise HTTPException(status_code=404, detail=f"unknown row {row_key}")
    history = list(
        session.scalars(
            select(OverrideValue).where(OverrideValue.row_key == row_key).order_by(OverrideValue.id.desc())
        )
    )
    log = status_log.entries(session, row_key)
    batch_key = (found.facts["material_no"], found.facts["batch_no"])
    deviations = session.execute(
        text(
            "SELECT deviation_no, title, severity, status, opened_on, closed_on, root_cause_category, "
            "causal_factor, investigation_summary, description, owner "
            "FROM mirror_deviations WHERE material_no = :m AND batch_no = :b ORDER BY deviation_no"
        ),
        {"m": batch_key[0], "b": batch_key[1]},
    ).mappings()
    changes = session.execute(
        text(
            "SELECT cc_no, title, status, current_state, proposed_state, opened_on, effective_on "
            "FROM mirror_change_controls WHERE material_no = :m AND batch_no = :b ORDER BY cc_no"
        ),
        {"m": batch_key[0], "b": batch_key[1]},
    ).mappings()
    samples = session.execute(
        text(
            "SELECT sample_id, status, collected_date, approved_at FROM mirror_samples "
            "WHERE row_key = :k ORDER BY sample_id"
        ),
        {"k": row_key},
    ).mappings()
    siblings = [
        RowOut.of(row, labels)
        for row in composed.rows
        if (row.facts["material_no"], row.facts["batch_no"]) == batch_key and row.row_key != row_key
    ]
    return RowDetail(
        **RowOut.of(found, labels).model_dump(),
        freshness=composed.freshness,
        facts=dict(found.facts),
        current_overrides={o.field: _override_out(o) for o in history if o.is_current},
        override_history=[_override_out(o) for o in history],
        status_log=[StatusLogOut.model_validate(e, from_attributes=True) for e in log],
        deviations=[DeviationOut(**d) for d in deviations],
        inbound_check=_inbound_check(session, row_key),
        changes=[ChangeControlOut(**c) for c in changes],
        samples=[SampleOut(**x) for x in samples],
        siblings=siblings,
    )


@router.put("/rows/{row_key}/need-by")
def put_need_by(
    row_key: str,
    body: NeedByIn,
    session: Annotated[Session, Depends(get_session, scope="function")],
    user: Annotated[AppUser, Depends(require_role(*PLANNERS))],
    profile: Annotated[SiteProfile, Depends(get_profile)],
) -> RowOut:
    overrides.set_need_by(
        session, user, row_key, body.adjusted_date, body.reason_code, body.expedite, body.note
    )
    return recomputed(session, profile, row_key)


@router.post("/rows/{row_key}/need-by/preview", dependencies=[Depends(current_user)])
def preview_need_by(
    row_key: str,
    body: NeedByIn,
    session: Annotated[Session, Depends(get_session, scope="function")],
    profile: Annotated[SiteProfile, Depends(get_profile)],
) -> PreviewOut:
    """Recompute the row with the proposed override, through the composition a read uses. Writes nothing."""
    overrides.require_open_row(session, row_key)
    if body.reason_code is not None:
        codes = set(session.scalars(text("SELECT code FROM mirror_reason_codes")))
        if body.reason_code not in codes:
            raise HTTPException(status_code=422, detail=f"unknown reason_code {body.reason_code!r}")
    composed = load_composed(session, profile)
    found = next((row for row in composed.rows if row.row_key == row_key), None)
    if found is None:
        raise HTTPException(status_code=404, detail=f"unknown row {row_key}")
    now = composed.now
    proposed = dict(found.overrides)
    proposed[ADJUSTED] = CurrentOverride(
        body.adjusted_date.isoformat() if body.adjusted_date else None,
        body.reason_code if body.adjusted_date else None,
        body.note,
        0,
        "preview",
        now,
    )
    proposed[EXPEDITE] = CurrentOverride(body.expedite, None, body.note, 0, "preview", now)
    after = compose_row(found.facts, proposed, _latest_of(found), found.status_log_count, profile, now)
    return PreviewOut(
        current=PlanOut.of(found.plan),
        preview=PlanOut.of(after.plan),
        system_need_by_locked=found.facts["system_need_by_locked"],
        operative_need_by=after.operative_need_by,
    )


@router.get("/rows/{row_key}/status-log", dependencies=[Depends(current_user)])
def get_status_log(
    row_key: str, session: Annotated[Session, Depends(get_session, scope="function")]
) -> StatusLogPage:
    status_log.require_row(session, row_key)
    found = [
        StatusLogOut.model_validate(e, from_attributes=True) for e in status_log.entries(session, row_key)
    ]
    return StatusLogPage(
        count=len(found), latest=next((e for e in found if e.status is not None), None), entries=found
    )


@router.post("/rows/{row_key}/status-log", status_code=201)
def post_status_log(
    row_key: str,
    body: StatusLogIn,
    session: Annotated[Session, Depends(get_session, scope="function")],
    user: Annotated[AppUser, Depends(require_role(*LOGGERS))],
    profile: Annotated[SiteProfile, Depends(get_profile)],
) -> StatusLogOut:
    entry = status_log.add_entry(
        session, profile, user, row_key, body.status, body.comment, body.team, body.reason_code
    )
    return StatusLogOut.model_validate(entry, from_attributes=True)


@router.post("/rows/{row_key}/hold")
def post_hold(
    row_key: str,
    body: ToggleIn,
    session: Annotated[Session, Depends(get_session, scope="function")],
    user: Annotated[AppUser, Depends(require_role(*HOLDERS))],
    profile: Annotated[SiteProfile, Depends(get_profile)],
) -> RowOut:
    overrides.set_hold(session, user, row_key, body.on, body.reason)
    return recomputed(session, profile, row_key)


@router.post("/rows/{row_key}/coa-release")
def post_coa_release(
    row_key: str,
    body: ToggleIn,
    session: Annotated[Session, Depends(get_session, scope="function")],
    user: Annotated[AppUser, Depends(require_role(*COA_RELEASERS))],
    profile: Annotated[SiteProfile, Depends(get_profile)],
) -> RowOut:
    overrides.set_coa_release(session, user, row_key, body.on, body.reason)
    return recomputed(session, profile, row_key)
