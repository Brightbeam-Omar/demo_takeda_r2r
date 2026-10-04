"""LIMS tables, ``04-data-contracts`` section 1.2."""

from datetime import date, datetime

from r2r_core.db import CounterMixin, TimestampMixin
from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Sample(TimestampMixin, Base):
    """A LIMS sample for an inspection lot. A rejected sample is retested by a new sample on the same lot."""

    __tablename__ = "sample"
    sample_id: Mapped[str] = mapped_column(Text, primary_key=True)  # S-0000001, counter-allocated
    inspection_lot_no: Mapped[str] = mapped_column(Text)  # ERP lot number (no FK: another database)
    material_no: Mapped[str] = mapped_column(Text)
    batch_no: Mapped[str] = mapped_column(Text)
    collected_date: Mapped[date] = mapped_column(Date)
    offsite_test: Mapped[bool] = mapped_column(Boolean)
    external_lab: Mapped[str | None] = mapped_column(Text)
    shipped_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(Text)  # registered, in_progress, approved, rejected
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        Index("ix_sample_material_batch", "material_no", "batch_no"),
        Index("ix_sample_lot", "inspection_lot_no"),
        CheckConstraint(
            "status in ('registered', 'in_progress', 'approved', 'rejected')", name="ck_sample_status"
        ),
    )


class TestResult(TimestampMixin, Base):
    """Individual test results of a sample. Empty in F04 (used by Tier 2 release readiness)."""

    __test__ = False  # not a pytest class
    __tablename__ = "test_result"
    id: Mapped[int] = mapped_column(primary_key=True)
    sample_id: Mapped[str] = mapped_column(ForeignKey("sample.sample_id"))
    test_code: Mapped[str] = mapped_column(Text)
    test_name: Mapped[str] = mapped_column(Text)
    result_value: Mapped[str] = mapped_column(Text)
    spec: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)  # pending, pass, fail, oos
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        Index("ix_test_result_sample", "sample_id"),
        CheckConstraint("status in ('pending', 'pass', 'fail', 'oos')", name="ck_test_result_status"),
    )


class Counter(CounterMixin, Base):
    """Number sequences (sample ids), so a reset restarts numbering."""

    __tablename__ = "counter"
