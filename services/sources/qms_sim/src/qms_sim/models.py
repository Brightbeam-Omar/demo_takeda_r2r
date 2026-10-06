"""QMS tables, ``04-data-contracts`` section 1.3 (CAPA is Tier 2; change control arrived in F19)."""

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
    severity: Mapped[str] = mapped_column(Text)  # minor, moderate, major (F19)
    status: Mapped[str] = mapped_column(Text)  # open, closed
    opened_on: Mapped[date] = mapped_column(Date)
    closed_on: Mapped[date | None] = mapped_column(Date)
    root_cause_category: Mapped[str] = mapped_column(Text)  # free text from a short generic list
    causal_factor: Mapped[str | None] = mapped_column(Text)  # F19
    investigation_summary: Mapped[str | None] = mapped_column(Text)  # F19
    owner: Mapped[str] = mapped_column(Text)  # a role name such as QA
    __table_args__ = (
        CheckConstraint("severity in ('minor', 'moderate', 'major')", name="ck_deviation_severity"),
        CheckConstraint("status in ('open', 'closed')", name="ck_deviation_status"),
    )


class DeviationLink(TimestampMixin, Base):
    """Links a deviation to a batch (material and batch number, as in the ERP)."""

    __tablename__ = "deviation_link"
    deviation_no: Mapped[str] = mapped_column(ForeignKey("deviation.deviation_no"), primary_key=True)
    material_no: Mapped[str] = mapped_column(Text, primary_key=True)
    batch_no: Mapped[str] = mapped_column(Text, primary_key=True)
    __table_args__ = (Index("ix_deviation_link_material_batch", "material_no", "batch_no"),)


class ChangeControl(TimestampMixin, Base):
    """A change control (F19-FR-03): the current and the proposed state, linked to batches."""

    __tablename__ = "change_control"
    cc_no: Mapped[str] = mapped_column(Text, primary_key=True)  # CC-000001, counter-allocated
    title: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)  # open, approved, closed, cancelled
    current_state: Mapped[str] = mapped_column(Text)
    proposed_state: Mapped[str] = mapped_column(Text)
    opened_on: Mapped[date] = mapped_column(Date)
    effective_on: Mapped[date | None] = mapped_column(Date)
    __table_args__ = (
        CheckConstraint(
            "status in ('open', 'approved', 'closed', 'cancelled')", name="ck_change_control_status"
        ),
    )


class ChangeControlLink(TimestampMixin, Base):
    """Links a change control to a batch (material and batch number, as in the ERP)."""

    __tablename__ = "change_control_link"
    cc_no: Mapped[str] = mapped_column(ForeignKey("change_control.cc_no"), primary_key=True)
    material_no: Mapped[str] = mapped_column(Text, primary_key=True)
    batch_no: Mapped[str] = mapped_column(Text, primary_key=True)
    __table_args__ = (Index("ix_change_control_link_material_batch", "material_no", "batch_no"),)


class Counter(CounterMixin, Base):
    """Number sequences (deviation and change control numbers), so a reset restarts numbering."""

    __tablename__ = "counter"
