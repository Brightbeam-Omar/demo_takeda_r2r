"""Human input: need-by overrides, manual status and comments (F09-FR-04, OQ-056, OQ-057).

Overrides are insert-only. A change inserts the next version and clears ``is_current`` on the previous one in
the same transaction, with one ``audit_event`` per changed field. Clearing is a new version with a null value.
Nothing here changes the mirror, the lakehouse or a source system (constitution P2).
"""

import datetime as dt
from typing import Any

from fastapi import HTTPException
from r2r_core import clock
from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from app_api.models import AppUser, AuditEvent, Comment, OverrideValue
from app_api.services.compose import ADJUSTED, EXPEDITE, MANUAL_HOLD, MANUAL_STATUS, RELEASE_ON_COA


def require_open_row(session: Session, row_key: str) -> str:
    """The row's stage key; 404 for an unknown row, 409 for a released one (nothing left to adjust)."""
    stage = session.execute(
        text("SELECT stage_key FROM mirror_batch_pipeline WHERE row_key = :row_key"), {"row_key": row_key}
    ).scalar()
    if stage is None:
        raise HTTPException(status_code=404, detail=f"unknown row {row_key}")
    terminal = session.execute(
        text("SELECT terminal FROM mirror_stage_reference WHERE stage_key = :stage"), {"stage": stage}
    ).scalar()
    if terminal:
        raise HTTPException(status_code=409, detail=f"row {row_key} is released")
    return str(stage)


def current(session: Session, row_key: str, field: str) -> OverrideValue | None:
    return session.scalars(
        select(OverrideValue).where(
            OverrideValue.row_key == row_key, OverrideValue.field == field, OverrideValue.is_current
        )
    ).first()


def _version(
    session: Session,
    user: AppUser,
    row_key: str,
    field: str,
    value: Any,
    reason_code: str | None,
    note: str | None,
    previous: OverrideValue | None,
) -> OverrideValue:
    version = 1
    if previous is not None:
        version = previous.version + 1
        session.execute(update(OverrideValue).where(OverrideValue.id == previous.id).values(is_current=False))
    elif (latest := _latest_version(session, row_key, field)) is not None:
        version = latest + 1  # every earlier version was superseded; cannot happen, but never reuse a number
    entry = OverrideValue(
        row_key=row_key,
        field=field,
        value_json=value,
        reason_code=reason_code,
        note=note,
        version=version,
        author_user_key=user.user_key,
        created_at=clock.now(),
        is_current=True,
    )
    session.add(entry)
    session.flush()
    return entry


def _latest_version(session: Session, row_key: str, field: str) -> int | None:
    return session.execute(
        text("SELECT max(version) FROM override_value WHERE row_key = :k AND field = :f"),
        {"k": row_key, "f": field},
    ).scalar()


def _audit(session: Session, user: AppUser, action: str, row_key: str, details: dict[str, Any]) -> None:
    session.add(
        AuditEvent(
            at=clock.now(),
            actor_user_key=user.user_key,
            action=action,
            row_key=row_key,
            details_json=details,
        )
    )


def set_need_by(
    session: Session,
    user: AppUser,
    row_key: str,
    adjusted_date: dt.date | None,
    reason_code: str | None,
    expedite: bool,
    note: str | None,
) -> None:
    """Apply a need-by PUT: only the fields that change get a version and an audit event."""
    require_open_row(session, row_key)
    if adjusted_date is not None:
        codes = set(session.scalars(text("SELECT code FROM mirror_reason_codes")))
        if not reason_code:
            raise HTTPException(status_code=422, detail="reason_code is required when a date is set")
        if reason_code not in codes:
            raise HTTPException(status_code=422, detail=f"unknown reason_code {reason_code!r}")

    previous = current(session, row_key, ADJUSTED)
    old_date = previous.value_json if previous is not None else None
    new_date = adjusted_date.isoformat() if adjusted_date else None
    old_reason = previous.reason_code if previous is not None else None
    date_changed = old_date != new_date or (new_date is not None and old_reason != reason_code)
    if date_changed:
        kept_reason = reason_code if new_date else None
        _version(session, user, row_key, ADJUSTED, new_date, kept_reason, note, previous)
        details = {
            "field": ADJUSTED,
            "old": old_date,
            "new": new_date,
            "reason_code": kept_reason,
            "note": note,
        }
        _audit(session, user, "need_by_set" if new_date else "need_by_cleared", row_key, details)

    previous_expedite = current(session, row_key, EXPEDITE)
    old_expedite = bool(previous_expedite and previous_expedite.value_json)
    if old_expedite != expedite:
        _version(session, user, row_key, EXPEDITE, expedite, None, note, previous_expedite)
        _audit(
            session, user, "expedite_set" if expedite else "expedite_cleared", row_key,
            {"field": EXPEDITE, "old": old_expedite, "new": expedite, "reason_code": None, "note": note},
        )  # fmt: skip


def set_status(
    session: Session, user: AppUser, row_key: str, rag: str | None, reason: str | None, team: str | None
) -> None:
    """Set or clear (``rag`` null) the manual status. It is display only (OQ-057)."""
    require_open_row(session, row_key)
    if rag is not None and not (reason and reason.strip()):
        raise HTTPException(status_code=422, detail="reason is required when a status is set")
    previous = current(session, row_key, MANUAL_STATUS)
    old = previous.value_json if previous is not None else None
    new = {"rag": rag, "team": team} if rag is not None else None
    if old == new and (new is None or (previous is not None and previous.note == reason)):
        return
    _version(session, user, row_key, MANUAL_STATUS, new, None, reason if new else None, previous)
    _audit(
        session, user, "status_set" if new else "status_cleared", row_key,
        {"field": MANUAL_STATUS, "old": old, "new": new, "reason_code": None, "note": reason},
    )  # fmt: skip


REASON_LENGTH = (3, 200)


def _clean_reason(reason: str) -> str:
    cleaned = reason.strip()
    low, high = REASON_LENGTH
    if not low <= len(cleaned) <= high:
        raise HTTPException(status_code=422, detail=f"reason must be {low}-{high} characters")
    return cleaned


def _require_cycle_start(session: Session, row_key: str) -> None:
    started = session.execute(
        text("SELECT cycle_start_date FROM mirror_batch_pipeline WHERE row_key = :k"), {"k": row_key}
    ).scalar()
    if started is None:
        raise HTTPException(status_code=409, detail=f"row {row_key} has no cycle start yet")


def _toggle(
    session: Session,
    user: AppUser,
    row_key: str,
    field: str,
    on: bool,
    reason: str,
    actions: tuple[str, str],
) -> None:
    """Switch a ``{"on", "reason"}`` override. A no-op is a 409; the audit row keeps the previous value."""
    cleaned = _clean_reason(reason)
    previous = current(session, row_key, field)
    was = previous.value_json if previous is not None else None
    if bool(was and was.get("on")) == on:
        state = "on" if on else "off"
        raise HTTPException(status_code=409, detail=f"{field} is already {state} for {row_key}")
    new = {"on": on, "reason": cleaned}
    _version(session, user, row_key, field, new, None, None, previous)
    _audit(
        session, user, actions[0] if on else actions[1], row_key,
        {"field": field, "reason": cleaned, "previous": was, "new": new},
    )  # fmt: skip


def set_hold(session: Session, user: AppUser, row_key: str, on: bool, reason: str) -> None:
    """Place or release a manual hold. Display only: the plan maths ignores it (F18-FR-09)."""
    require_open_row(session, row_key)  # 404 unknown, 409 released
    _toggle(session, user, row_key, MANUAL_HOLD, on, reason, ("hold_placed", "hold_released"))


def set_coa_release(session: Session, user: AppUser, row_key: str, on: bool, reason: str) -> None:
    """Set or undo Release on COA. The plan then uses the profile's single COA deadline (F18-FR-10)."""
    require_open_row(session, row_key)
    _require_cycle_start(session, row_key)
    _toggle(session, user, row_key, RELEASE_ON_COA, on, reason, ("coa_release_set", "coa_release_cleared"))


def add_comment(session: Session, user: AppUser, row_key: str, body: str) -> Comment:
    if (
        session.execute(
            text("SELECT 1 FROM mirror_batch_pipeline WHERE row_key = :k"), {"k": row_key}
        ).first()
        is None
    ):
        raise HTTPException(status_code=404, detail=f"unknown row {row_key}")
    if not body.strip():
        raise HTTPException(status_code=422, detail="a comment cannot be empty")
    comment = Comment(
        row_key=row_key, body=body.strip(), author_user_key=user.user_key, created_at=clock.now()
    )
    session.add(comment)
    session.flush()
    _audit(session, user, "comment_added", row_key, {"comment_id": comment.id})
    return comment
