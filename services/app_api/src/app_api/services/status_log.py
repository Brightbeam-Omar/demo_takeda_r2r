"""The status log (F19-FR-05, OQ-111): one insert-only log of status updates and comments per row.

Every role except ``viewer`` may add an entry. The latest entry *with a status* is the ``latest_status``.
The old ``manual_status`` and comment endpoints are thin wrappers over ``add_entry``.
"""

from fastapi import HTTPException
from r2r_core import clock
from r2r_core.profile import SiteProfile
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app_api.models import AppUser, AuditEvent, StatusLog


def require_row(session: Session, row_key: str) -> None:
    found = session.execute(
        text("SELECT 1 FROM mirror_batch_pipeline WHERE row_key = :k"), {"k": row_key}
    ).first()
    if found is None:
        raise HTTPException(status_code=404, detail=f"unknown row {row_key}")


def entries(session: Session, row_key: str) -> list[StatusLog]:
    """Every entry of the row, newest first."""
    return list(
        session.scalars(select(StatusLog).where(StatusLog.row_key == row_key).order_by(StatusLog.id.desc()))
    )


def add_entry(
    session: Session,
    profile: SiteProfile,
    user: AppUser,
    row_key: str,
    status: str | None,
    comment: str,
    team: str | None = None,
    reason_code: str | None = None,
) -> StatusLog:
    """Validate and append one entry, with its ``status_logged`` audit event."""
    require_row(session, row_key)
    cleaned = comment.strip()
    if not cleaned:
        raise HTTPException(status_code=422, detail="a comment is required")
    if status is not None and status not in {o.key for o in profile.status_options}:
        raise HTTPException(status_code=422, detail=f"unknown status {status!r}")
    if reason_code is not None and reason_code not in {r.key for r in profile.status_reasons}:
        raise HTTPException(status_code=422, detail=f"unknown reason {reason_code!r}")
    if team is not None:
        teams = set(session.scalars(text("SELECT DISTINCT team FROM mirror_stage_reference")))
        if team not in teams:
            raise HTTPException(status_code=422, detail=f"unknown team {team!r}")
    entry = StatusLog(
        row_key=row_key,
        status=status,
        team=team,
        reason_code=reason_code,
        comment=cleaned,
        author_user_key=user.user_key,
        at=clock.now(),
    )
    session.add(entry)
    session.flush()
    session.add(
        AuditEvent(
            at=clock.now(),
            actor_user_key=user.user_key,
            action="status_logged",
            row_key=row_key,
            details_json={
                "comment_id": entry.id,
                "status": status,
                "team": team,
                "reason_code": reason_code,
                "comment": cleaned,
            },
        )
    )
    return entry
