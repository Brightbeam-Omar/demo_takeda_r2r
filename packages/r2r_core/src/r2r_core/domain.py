"""Domain types shared by every service [F03-FR-04].

Stage keys come from the site profile at runtime, so ``StageKey`` is a typed string, not an enum.
Everything else is a ``StrEnum`` whose values match the published contract and the app database.
"""

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from typing import NewType

from r2r_core.profile import SiteProfile

StageKey = NewType("StageKey", str)


def stage_keys(profile: SiteProfile) -> list[StageKey]:
    """Stage keys in the profile's sort order."""
    return [StageKey(stage.key) for stage in profile.stages]


class LotType(StrEnum):
    INITIAL = "01"  # initial receipt inspection
    REEVAL = "09"  # periodic re-evaluation


class Rag(StrEnum):
    GREEN = "green"
    AMBER = "amber"
    RED = "red"


class Role(StrEnum):
    PLANNER = "planner"
    QC_LEAD = "qc_lead"
    QA_RELEASE = "qa_release"
    VIEWER = "viewer"
    ADMIN = "admin"


class OverrideField(StrEnum):
    ADJUSTED_NEED_BY_DATE = "adjusted_need_by_date"
    EXPEDITE = "expedite"
    MANUAL_STATUS = "manual_status"
    DELIVERY_DATE = "delivery_date"
    DELIVERY_LOCATION = "delivery_location"


@dataclass(frozen=True, kw_only=True)
class RowFacts:
    """The published-row fields the SLA maths and the air-gap check need (published column names)."""

    row_key: str
    stage_key: StageKey
    lot_type: LotType
    received_location_type: str
    offsite: bool
    current_stage_entry_date: date | None
    system_need_by_locked: date | None
    on_hold: bool
    ud_rejected: bool
    lims_status: str
    ud_effective: bool
    ud_code: str | None
    lims_approved_at: datetime | None
    cycle_start_date: date | None = None  # F18: the Release on COA deadline counts from here
