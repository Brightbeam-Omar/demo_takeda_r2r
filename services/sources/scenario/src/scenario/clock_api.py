"""Clock endpoints (F04-FR-07). The clock lives in ``app.demo_clock`` and moves only through ``set`` or
``advance``; it never ticks with wall time. ``GET /clock`` is open; both ``POST``s need the scenario token.
"""

import os
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, PositiveInt, StrictStr, field_validator, model_validator
from r2r_core.profile import SiteProfile, load_profile
from r2r_core.web import require_scenario_token
from sqlalchemy import Engine, text


class ClockOut(BaseModel):
    now_utc: datetime
    today_local: date
    frozen: bool


class SetIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    iso: StrictStr  # timezone-aware ISO 8601; naive input is rejected (422)

    @field_validator("iso")
    @classmethod
    def _aware_iso(cls, value: str) -> str:
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as error:
            raise ValueError("iso must be an ISO 8601 datetime") from error
        if parsed.tzinfo is None:
            raise ValueError("iso must include a timezone offset")
        return value

    @property
    def moment(self) -> datetime:
        return datetime.fromisoformat(self.iso).astimezone(UTC)


class AdvanceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hours: PositiveInt | None = None
    days: PositiveInt | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> "AdvanceIn":
        if (self.hours is None) == (self.days is None):
            raise ValueError("give exactly one of hours or days")
        return self

    @property
    def total_hours(self) -> int:
        return self.hours if self.hours is not None else (self.days or 0) * 24


def default_profile() -> SiteProfile:
    return load_profile(os.environ.get("SITE_PROFILE", "site_a"))


def seed_clock(engine: Engine, profile: SiteProfile) -> None:
    """Insert the clock row from the profile's opening time if there is none. Never overwrites."""
    start = profile.demo.start_datetime.astimezone(UTC)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO demo_clock (id, now_utc, frozen) VALUES (1, :start, false) "
                "ON CONFLICT (id) DO NOTHING"
            ),
            {"start": start},
        )


def build_router(engine: Engine, profile: SiteProfile) -> APIRouter:
    router = APIRouter(tags=["clock"])

    def output(now_utc: datetime, frozen: bool) -> ClockOut:
        local_date = now_utc.astimezone(profile.site.tz).date()
        return ClockOut(now_utc=now_utc, today_local=local_date, frozen=frozen)

    def run(sql: str, **params: object) -> ClockOut:
        with engine.begin() as connection:
            row = connection.execute(text(sql), params).one_or_none()
        if row is None:
            raise HTTPException(status_code=503, detail="demo_clock has no row yet")
        return output(row.now_utc, row.frozen)

    @router.get("/clock")
    def get_clock() -> ClockOut:
        return run("SELECT now_utc, frozen FROM demo_clock WHERE id = 1")

    guard = [Depends(require_scenario_token)]

    @router.post("/clock/set", dependencies=guard)
    def set_clock(body: SetIn) -> ClockOut:
        return run(
            "UPDATE demo_clock SET now_utc = :moment WHERE id = 1 RETURNING now_utc, frozen",
            moment=body.moment,
        )

    @router.post("/clock/advance", dependencies=guard)
    def advance_clock(body: AdvanceIn) -> ClockOut:
        # One atomic statement: hours are exact, so "days: 1" moves the clock by exactly 24 h.
        return run(
            "UPDATE demo_clock SET now_utc = now_utc + :hours * interval '1 hour' WHERE id = 1 "
            "RETURNING now_utc, frozen",
            hours=body.total_hours,
        )

    return router
