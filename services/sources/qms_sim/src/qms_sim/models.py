"""QMS tables, ``04-data-contracts`` section 1.3 (CAPA and change control are Tier 2)."""

from datetime import date

from r2r_core.db import CounterMixin, TimestampMixin
from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Deviation(TimestampMixin, Base):
    __tablename__ = "deviation"
    deviation_no: Mapped[str] = mapped_column(Text, primary_key=True)  # DEV-000001, counter-allocated
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(Text)  # minor, major, critical
    status: Mapped[str] = mapped_column(Text)  # open, closed
    opened_on: Mapped[date] = mapped_column(Date)
    closed_on: Mapped[date | None] = mapped_column(Date)
    root_cause_category: Mapped[str] = mapped_column(Text)  # free text from a short generic list
    owner: Mapped[str] = mapped_column(Text)  # a role name such as QA
    __table_args__ = (
        CheckConstraint("severity in ('minor', 'major', 'critical')", name="ck_deviation_severity"),
        CheckConstraint("status in ('open', 'closed')", name="ck_deviation_status"),
    )


class DeviationLink(TimestampMixin, Base):
    """Links a deviation to a batch (material and batch number, as in the ERP)."""

    __tablename__ = "deviation_link"
    deviation_no: Mapped[str] = mapped_column(ForeignKey("deviation.deviation_no"), primary_key=True)
    material_no: Mapped[str] = mapped_column(Text, primary_key=True)
    batch_no: Mapped[str] = mapped_column(Text, primary_key=True)
    __table_args__ = (Index("ix_deviation_link_material_batch", "material_no", "batch_no"),)


class Counter(CounterMixin, Base):
    """Number sequences (deviation numbers), so a reset restarts numbering."""

    __tablename__ = "counter"
