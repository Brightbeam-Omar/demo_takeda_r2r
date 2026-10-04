"""Request bodies of the LIMS event endpoints (F04-FR-04). Business dates default to the demo's today."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict


class Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SampleCollectedIn(Body):
    inspection_lot_no: str
    material_no: str
    batch_no: str
    collected_date: date | None = None
    offsite_test: bool = False
    external_lab: str | None = None  # required for offsite tests, not allowed otherwise
    sample_id: str | None = None  # explicit id; default: next S-0000001-style number


class SampleShippedIn(Body):
    sample_id: str
    shipped_date: date | None = None


class SampleRef(Body):
    sample_id: str


class TestResultIn(Body):
    __test__ = False  # not a pytest class
    sample_id: str
    test_code: str
    test_name: str
    result_value: str
    spec: str
    status: Literal["pending", "pass", "fail", "oos"] = "pass"
    completed_on: date | None = None  # default: today when the status is not pending
