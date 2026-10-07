"""What a run needs, built once at start-up and shared by the routes (tests replace single parts)."""

from dataclasses import dataclass
from datetime import date, datetime

from r2r_core import clock
from r2r_core.profile import SiteProfile
from sqlalchemy import Engine

from agents.air_gap.validator import ValidationContext
from agents.gateway.base import ModelGateway
from agents.settings import Settings
from agents.tools.http import ReadOnlyHttp


@dataclass
class Deps:
    settings: Settings
    engine: Engine
    http: ReadOnlyHttp
    gateway: ModelGateway
    profile: SiteProfile

    def validation_context(self, demo_user: str | None) -> ValidationContext:
        now: datetime = clock.now()
        today: date = clock.today()
        return ValidationContext(
            http=self.http,
            demo_user=demo_user,
            threshold_hours=self.profile.air_gap.threshold_hours,
            high_priority_days=self.profile.agents.air_gap.high_priority_days,
            now=now,
            today=today,
        )
