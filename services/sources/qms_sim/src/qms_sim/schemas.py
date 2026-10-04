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
    severity: Literal["minor", "major", "critical"]
    opened_on: date | None = None
    root_cause_category: str = ""
    owner: str = "QA"
    links: list[BatchLink] = []
    deviation_no: str | None = None  # explicit number; default: next DEV-000001-style number


class DeviationClosedIn(Body):
    deviation_no: str
    closed_on: date | None = None
