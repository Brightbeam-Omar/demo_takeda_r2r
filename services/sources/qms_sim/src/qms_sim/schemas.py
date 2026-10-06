"""Request bodies of the QMS event endpoints (F04-FR-05). Business dates default to the demo's today."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict


class Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BatchLink(Body):
    material_no: str
    batch_no: str


class DeviationOpenedIn(Body):
    title: str
    description: str = ""
    severity: Literal["minor", "moderate", "major"]
    opened_on: date | None = None
    root_cause_category: str = ""
    owner: str = "QA"
    causal_factor: str | None = None  # F19
    investigation_summary: str | None = None  # F19
    links: list[BatchLink] = []
    deviation_no: str | None = None  # explicit number; default: next DEV-000001-style number


class DeviationClosedIn(Body):
    deviation_no: str
    closed_on: date | None = None
    investigation_summary: str | None = None  # F19: set when the investigation is written up


ChangeControlStatus = Literal["open", "approved", "closed", "cancelled"]


class ChangeControlOpenedIn(Body):
    title: str
    current_state: str
    proposed_state: str
    status: ChangeControlStatus = "open"
    opened_on: date | None = None
    effective_on: date | None = None
    links: list[BatchLink] = []
    cc_no: str | None = None  # explicit number; default: next CC-000001-style number


class ChangeControlStatusIn(Body):
    cc_no: str
    status: ChangeControlStatus
    effective_on: date | None = None  # default: unchanged
