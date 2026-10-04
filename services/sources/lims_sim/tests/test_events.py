"""T5: LIMS event functions [F04-FR-04, F04-AC-06]. Needs Postgres (integration)."""

from datetime import UTC, date, datetime

import pytest
from lims_sim import events, schemas
from lims_sim.models import Sample
from r2r_core import clock
from r2r_core.clock import FixedClock
from r2r_core.errors import Conflict, Invalid
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

pytestmark = pytest.mark.integration

DEMO_NOW = datetime(2026, 10, 12, 7, 0, tzinfo=UTC)
LOT = {"inspection_lot_no": "10000001", "material_no": "RM10001", "batch_no": "B1001"}


def collect(session: Session, **overrides: object) -> str:
    result = events.sample_collected(session, schemas.SampleCollectedIn(**{**LOT, **overrides}))
    return str(result["sample"]["sample_id"])


def ref(sample_id: str) -> schemas.SampleRef:
    return schemas.SampleRef(sample_id=sample_id)


def test_f04_fr04_sample_collected_registers_a_sample_with_a_counter_id(
    factory: sessionmaker[Session],
) -> None:
    with factory() as session:
        first = collect(session)
        second = collect(session, inspection_lot_no="10000002")
        session.commit()
        sample = session.get(Sample, first)
        assert sample is not None
        assert (first, second) == ("S-0000001", "S-0000002")
        assert (sample.status, sample.collected_date, sample.offsite_test, sample.approved_at) == (
            "registered", date(2026, 10, 12), False, None,
        )  # fmt: skip
        assert sample.updated_at == DEMO_NOW


def test_f04_ac06_approved_sets_the_status_and_approved_at_to_demo_now(
    factory: sessionmaker[Session],
) -> None:
    """F04-AC-06."""
    with factory() as session:
        sample_id = collect(session)
        events.testing_started(session, ref(sample_id))
        later = datetime(2026, 10, 14, 15, 30, tzinfo=UTC)
        clock.set_clock_source(FixedClock(later))
        events.approved(session, ref(sample_id))
        session.commit()
        sample = session.get(Sample, sample_id)
        assert sample is not None
        assert sample.status == "approved"
        assert sample.approved_at == later


def test_f04_fr04_approval_works_straight_from_registered(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        sample_id = collect(session)
        events.approved(session, ref(sample_id))
        assert session.get(Sample, sample_id).status == "approved"  # type: ignore[union-attr]


def test_f04_fr04_offsite_samples_are_shipped_before_testing_or_approval(
    factory: sessionmaker[Session],
) -> None:
    with factory() as session:
        sample_id = collect(session, offsite_test=True, external_lab="External Lab A")
        with pytest.raises(Invalid, match="not been shipped"):
            events.testing_started(session, ref(sample_id))
        with pytest.raises(Invalid, match="not been shipped"):
            events.approved(session, ref(sample_id))
        events.sample_shipped(
            session, schemas.SampleShippedIn(sample_id=sample_id, shipped_date=date(2026, 10, 10))
        )
        events.testing_started(session, ref(sample_id))
        session.commit()
        sample = session.get(Sample, sample_id)
        assert sample is not None
        assert (sample.status, sample.shipped_date) == ("in_progress", date(2026, 10, 10))


def test_f04_fr04_shipping_rules(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        onsite = collect(session)
        with pytest.raises(Invalid, match="onsite"):
            events.sample_shipped(session, schemas.SampleShippedIn(sample_id=onsite))
        offsite = collect(
            session, inspection_lot_no="10000002", offsite_test=True, external_lab="External Lab B"
        )
        events.sample_shipped(session, schemas.SampleShippedIn(sample_id=offsite))
        with pytest.raises(Invalid, match="already shipped"):
            events.sample_shipped(session, schemas.SampleShippedIn(sample_id=offsite))
        assert session.get(Sample, offsite).shipped_date == date(2026, 10, 12)  # type: ignore[union-attr]


def test_f04_fr04_offsite_and_lab_must_agree(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        with pytest.raises(Invalid, match="external_lab"):
            collect(session, offsite_test=True)
        with pytest.raises(Invalid, match="only for offsite"):
            collect(session, external_lab="External Lab A")


def test_f04_oq030_a_rejected_sample_is_retested_by_a_new_sample_and_the_latest_has_the_highest_id(
    factory: sessionmaker[Session],
) -> None:
    with factory() as session:
        first = collect(session)
        with pytest.raises(Invalid, match="active sample"):
            collect(session)
        events.rejected(session, ref(first))
        retest = collect(session)
        session.commit()
        ids = list(session.scalars(select(Sample.sample_id).where(Sample.inspection_lot_no == "10000001")))
        assert retest > first
        assert max(ids) == retest


def test_f04_fr04_finished_samples_cannot_change_again(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        sample_id = collect(session)
        events.approved(session, ref(sample_id))
        for step in (events.approved, events.rejected, events.testing_started):
            with pytest.raises(Invalid, match="approved"):
                step(session, ref(sample_id))
        with pytest.raises(Invalid, match="unknown sample"):
            events.approved(session, ref("S-9999999"))


def test_f04_fr04_testing_cannot_start_twice(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        sample_id = collect(session)
        events.testing_started(session, ref(sample_id))
        with pytest.raises(Invalid, match="in progress"):
            events.testing_started(session, ref(sample_id))


def test_f04_fr10_explicit_sample_ids_are_used_and_duplicates_conflict(
    factory: sessionmaker[Session],
) -> None:
    with factory() as session:
        assert collect(session, sample_id="S-0000077") == "S-0000077"
        with pytest.raises(Conflict):
            collect(session, inspection_lot_no="10000002", sample_id="S-0000077")


def test_f05_test_result_recorded_adds_a_result_to_a_sample(factory: sessionmaker[Session]) -> None:
    from lims_sim.models import TestResult

    with factory() as session:
        sample_id = collect(session)
        body = schemas.TestResultIn(
            sample_id=sample_id,
            test_code="ASSAY",
            test_name="Assay",
            result_value="99.1 %",
            spec="98.0-102.0 %",
        )
        done = events.test_result_recorded(session, body)["test_result"]
        pending = events.test_result_recorded(
            session, schemas.TestResultIn(**{**body.model_dump(), "status": "pending"})
        )["test_result"]
        session.commit()
        row = session.get(TestResult, done["id"])
        assert row is not None
        assert (row.status, row.completed_at, row.updated_at) == ("pass", DEMO_NOW, DEMO_NOW)
        assert pending["completed_at"] is None


def test_f05_test_result_for_an_unknown_sample_is_invalid(factory: sessionmaker[Session]) -> None:
    body = schemas.TestResultIn(
        sample_id="S-9999999", test_code="A", test_name="A", result_value="1", spec="1"
    )
    with factory() as session, pytest.raises(Invalid):
        events.test_result_recorded(session, body)
