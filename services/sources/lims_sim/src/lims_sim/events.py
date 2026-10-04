"""LIMS event functions (F04-FR-04). Same conventions as the ERP: one transaction per event, ``updated_at``
from ``r2r_core.clock.now()`` through the session, business dates defaulting to the demo's today.

The latest sample for a lot is the one with the highest ``sample_id``.
"""

from typing import Any

from r2r_core import clock
from r2r_core.db import allocate_number, row_dict
from r2r_core.errors import Conflict, Invalid
from sqlalchemy import select
from sqlalchemy.orm import Session

from lims_sim import schemas
from lims_sim.models import Counter, Sample, TestResult

OPEN_STATUSES = ("registered", "in_progress")


def _sample(session: Session, sample_id: str) -> Sample:
    found = session.get(Sample, sample_id)
    if found is None:
        raise Invalid(f"unknown sample {sample_id}")
    return found


def _open_sample(session: Session, sample_id: str) -> Sample:
    sample = _sample(session, sample_id)
    if sample.status not in OPEN_STATUSES:
        raise Invalid(f"sample {sample_id} is {sample.status}")
    return sample


def _require_shipped(sample: Sample) -> None:
    if sample.offsite_test and sample.shipped_date is None:
        raise Invalid(f"offsite sample {sample.sample_id} has not been shipped yet")


def sample_collected(session: Session, body: schemas.SampleCollectedIn) -> dict[str, Any]:
    """Register a new sample for a lot. A lot gets a new sample only if its latest one was rejected."""
    if body.offsite_test and not body.external_lab:
        raise Invalid("an offsite test needs an external_lab")
    if not body.offsite_test and body.external_lab:
        raise Invalid("external_lab is only for offsite tests")
    lot_samples = select(Sample).where(Sample.inspection_lot_no == body.inspection_lot_no)
    latest = session.scalars(lot_samples.order_by(Sample.sample_id.desc())).first()
    if latest is not None and latest.status != "rejected":
        raise Invalid(f"lot {body.inspection_lot_no} already has an active sample ({latest.sample_id})")

    def taken(number: str) -> bool:
        return session.get(Sample, number) is not None

    if body.sample_id is not None:
        if taken(body.sample_id):
            raise Conflict(f"sample {body.sample_id} already exists")
        sample_id = body.sample_id
    else:
        sample_id = allocate_number(session, Counter, "sample", lambda n: f"S-{n:07d}", exists=taken)
    sample = Sample(
        sample_id=sample_id,
        inspection_lot_no=body.inspection_lot_no,
        material_no=body.material_no,
        batch_no=body.batch_no,
        collected_date=body.collected_date or clock.today(),
        offsite_test=body.offsite_test,
        external_lab=body.external_lab,
        shipped_date=None,
        status="registered",
        approved_at=None,
    )
    session.add(sample)
    session.flush()
    return {"sample": row_dict(sample)}


def sample_shipped(session: Session, body: schemas.SampleShippedIn) -> dict[str, Any]:
    sample = _open_sample(session, body.sample_id)
    if not sample.offsite_test:
        raise Invalid(f"sample {sample.sample_id} is tested onsite: nothing to ship")
    if sample.shipped_date is not None:
        raise Invalid(f"sample {sample.sample_id} was already shipped")
    sample.shipped_date = body.shipped_date or clock.today()
    session.flush()
    return {"sample": row_dict(sample)}


def testing_started(session: Session, body: schemas.SampleRef) -> dict[str, Any]:
    sample = _open_sample(session, body.sample_id)
    if sample.status != "registered":
        raise Invalid(f"sample {sample.sample_id} is already in progress")
    _require_shipped(sample)
    sample.status = "in_progress"
    session.flush()
    return {"sample": row_dict(sample)}


def approved(session: Session, body: schemas.SampleRef) -> dict[str, Any]:
    """All tests complete and approved. ``approved_at`` is the demo clock's now."""
    sample = _open_sample(session, body.sample_id)
    _require_shipped(sample)
    sample.status = "approved"
    sample.approved_at = clock.now()
    session.flush()
    return {"sample": row_dict(sample)}


def rejected(session: Session, body: schemas.SampleRef) -> dict[str, Any]:
    sample = _open_sample(session, body.sample_id)
    sample.status = "rejected"
    session.flush()
    return {"sample": row_dict(sample)}


def test_result_recorded(session: Session, body: schemas.TestResultIn) -> dict[str, Any]:
    """Record one test result for a sample. Added in F05 so seeded results also go through an event."""
    sample = _sample(session, body.sample_id)
    done = body.completed_on or clock.today()
    result = TestResult(
        sample_id=sample.sample_id,
        test_code=body.test_code,
        test_name=body.test_name,
        result_value=body.result_value,
        spec=body.spec,
        status=body.status,
        completed_at=None
        if body.status == "pending"
        else clock.now().replace(year=done.year, month=done.month, day=done.day),
    )
    session.add(result)
    session.flush()
    return {"test_result": row_dict(result)}
