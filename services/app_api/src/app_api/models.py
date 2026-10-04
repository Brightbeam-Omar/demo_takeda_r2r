"""Tables of the ``app`` database. F04 owns only ``demo_clock``; F08 extends this module."""

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, false
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class DemoClock(Base):
    """The demo clock: one row. It moves only through the scenario service (set or advance).

    No ``updated_at``: this table *is* the clock.
    """

    __tablename__ = "demo_clock"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    now_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    frozen: Mapped[bool] = mapped_column(Boolean, server_default=false())  # reserved; always false for now
    __table_args__ = (CheckConstraint("id = 1", name="ck_demo_clock_single_row"),)
