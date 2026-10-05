"""Loads the composed rows: the mirror, the current overrides and the comment counts, through ``compose``.

The mirror is small (about 800 rows), so the composed rows are cached for ``CACHE_SECONDS`` per
``(contract run, newest override, newest comment, demo clock to the second)`` (OQ-061): a new run, a human
edit or a clock advance is visible at once, and a burst of reads shares one composition.
"""

import datetime as dt
import threading
import time
from dataclasses import dataclass
from typing import Any

from r2r_core import clock
from r2r_core.profile import SiteProfile
from sqlalchemy import text
from sqlalchemy.orm import Session

from app_api.schemas import Freshness
from app_api.services.compose import ComposedRow, CurrentOverride, compose_rows

CACHE_SECONDS = 5.0


@dataclass(frozen=True)
class Composed:
    rows: list[ComposedRow]
    freshness: Freshness
    today: dt.date
    now: dt.datetime


_lock = threading.Lock()
_cache: dict[str, Any] = {"key": None, "at": 0.0, "value": None}


def clear_cache() -> None:
    with _lock:
        _cache.update(key=None, at=0.0, value=None)


def _status(session: Session) -> Any:
    return session.execute(
        text("SELECT last_run_id, last_success_at FROM mirror_pipeline_status LIMIT 1")
    ).first()


def freshness(session: Session, now: dt.datetime) -> Freshness:
    status = _status(session)
    if status is None:
        return Freshness(contract_run_id=None, last_success_at=None, freshness_minutes=None)
    minutes = max(0, int((now - status.last_success_at).total_seconds() // 60))
    return Freshness(
        contract_run_id=status.last_run_id, last_success_at=status.last_success_at, freshness_minutes=minutes
    )


def load_composed(session: Session, profile: SiteProfile) -> Composed:
    now = clock.now()
    today = now.astimezone(profile.site.tz).date()
    status = _status(session)
    newest = session.execute(
        text(
            "SELECT (SELECT max(id) FROM override_value) AS override_id, "
            "(SELECT max(id) FROM comment) AS comment_id"
        )
    ).one()
    run_id = status.last_run_id if status else None
    key = (run_id, newest.override_id, newest.comment_id, now.replace(microsecond=0))
    with _lock:
        if _cache["key"] == key and time.monotonic() - _cache["at"] < CACHE_SECONDS:
            cached: Composed = _cache["value"]
            return cached
    value = _compose(session, profile, now, today, freshness(session, now))
    with _lock:
        _cache.update(key=key, at=time.monotonic(), value=value)
    return value


def _compose(
    session: Session, profile: SiteProfile, now: dt.datetime, today: dt.date, fresh: Freshness
) -> Composed:
    mirror = [dict(r) for r in session.execute(text("SELECT * FROM mirror_batch_pipeline")).mappings()]
    overrides: dict[str, dict[str, CurrentOverride]] = {}
    for r in session.execute(
        text(
            "SELECT row_key, field, value_json, reason_code, note, version, author_user_key, created_at "
            "FROM override_value WHERE is_current"
        )
    ):
        overrides.setdefault(r.row_key, {})[r.field] = CurrentOverride(
            r.value_json, r.reason_code, r.note, r.version, r.author_user_key, r.created_at
        )
    counted = session.execute(text("SELECT row_key, count(*) FROM comment GROUP BY row_key"))
    counts = {row_key: total for row_key, total in counted.tuples()}
    rows = compose_rows(mirror, overrides, counts, profile, now)
    return Composed(rows=rows, freshness=fresh, today=today, now=now)
