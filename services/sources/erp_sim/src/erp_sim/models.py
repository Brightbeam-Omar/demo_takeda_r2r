"""ERP tables, ``04-data-contracts`` section 1.1. Names are SAP-style on purpose, so ERP-literate
audiences recognise the shape; each table carries a comment saying what it is.
"""

from datetime import date, datetime
from decimal import Decimal

from r2r_core.db import CounterMixin, TimestampMixin
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

QTY = Numeric(13, 3)


class Base(DeclarativeBase):
    pass


class Mara(TimestampMixin, Base):
    """Material master."""

    __tablename__ = "mara"
    matnr: Mapped[str] = mapped_column(Text, primary_key=True)  # material number
    maktx: Mapped[str] = mapped_column(Text)  # description
    mtart: Mapped[str] = mapped_column(Text)  # ROH raw / CONS consumable
    zmolty: Mapped[str] = mapped_column(Text)  # molecule type
    zclass: Mapped[str] = mapped_column(Text)  # material class


class Lfa1(TimestampMixin, Base):
    """Supplier master."""

    __tablename__ = "lfa1"
    lifnr: Mapped[str] = mapped_column(Text, primary_key=True)  # supplier id, e.g. SUP001
    name1: Mapped[str] = mapped_column(Text)
    land1: Mapped[str] = mapped_column(Text)  # country


class T001l(TimestampMixin, Base):
    """Storage locations."""

    __tablename__ = "t001l"
    lgort: Mapped[str] = mapped_column(Text, primary_key=True)  # e.g. 0100
    lgobe: Mapped[str] = mapped_column(Text)  # name
    zloctype: Mapped[str] = mapped_column(Text)  # onsite / 3pl
    __table_args__ = (CheckConstraint("zloctype in ('onsite', '3pl')", name="ck_t001l_zloctype"),)


class Mcha(TimestampMixin, Base):
    """Batch master."""

    __tablename__ = "mcha"
    matnr: Mapped[str] = mapped_column(ForeignKey("mara.matnr"), primary_key=True)
    charg: Mapped[str] = mapped_column(Text, primary_key=True)  # batch
    lifnr: Mapped[str] = mapped_column(ForeignKey("lfa1.lifnr"))
    licha: Mapped[str] = mapped_column(Text)  # supplier batch
    hsdat: Mapped[date | None] = mapped_column(Date)  # manufacture date
    vfdat: Mapped[date | None] = mapped_column(Date)  # expiry
    zstat: Mapped[str] = mapped_column(Text, default="", server_default="")  # '' or 'H' (hold)
    qnext: Mapped[date | None] = mapped_column(Date)  # next inspection (retest) date (F18, OQ-100)
    __table_args__ = (CheckConstraint("zstat in ('', 'H')", name="ck_mcha_zstat"),)


class Mchb(TimestampMixin, Base):
    """Current stock per batch and storage location."""

    __tablename__ = "mchb"
    matnr: Mapped[str] = mapped_column(Text, primary_key=True)
    charg: Mapped[str] = mapped_column(Text, primary_key=True)
    lgort: Mapped[str] = mapped_column(ForeignKey("t001l.lgort"), primary_key=True)
    insme: Mapped[Decimal] = mapped_column(QTY, default=Decimal(0))  # quality inspection (QI)
    speme: Mapped[Decimal] = mapped_column(QTY, default=Decimal(0))  # blocked
    clabs: Mapped[Decimal] = mapped_column(QTY, default=Decimal(0))  # unrestricted
    __table_args__ = (
        ForeignKeyConstraint(["matnr", "charg"], ["mcha.matnr", "mcha.charg"]),
        CheckConstraint("insme >= 0 and speme >= 0 and clabs >= 0", name="ck_mchb_non_negative"),
    )


class Mseg(TimestampMixin, Base):
    """Material document lines. 101 GR, 102 GR reversal, 311 transfer."""

    __tablename__ = "mseg"
    mblnr: Mapped[str] = mapped_column(Text, primary_key=True)  # material document
    zeile: Mapped[str] = mapped_column(Text, primary_key=True)  # line
    bwart: Mapped[str] = mapped_column(Text)  # movement type
    matnr: Mapped[str] = mapped_column(Text)
    charg: Mapped[str] = mapped_column(Text)
    lgort: Mapped[str] = mapped_column(ForeignKey("t001l.lgort"))  # 101/102 receiving; 311 source
    umlgo: Mapped[str | None] = mapped_column(ForeignKey("t001l.lgort"))  # 311 destination
    budat: Mapped[date] = mapped_column(Date)  # posting date
    menge: Mapped[Decimal] = mapped_column(QTY)  # quantity
    ebeln: Mapped[str | None] = mapped_column(Text)  # purchase order the 101 was received against
    ebelp: Mapped[str | None] = mapped_column(Text)  # purchase order line
    __table_args__ = (
        ForeignKeyConstraint(["matnr", "charg"], ["mcha.matnr", "mcha.charg"]),
        Index("ix_mseg_matnr_charg", "matnr", "charg"),
        CheckConstraint("bwart in ('101', '102', '311')", name="ck_mseg_bwart"),
        CheckConstraint("menge > 0", name="ck_mseg_menge"),
    )


class Qals(TimestampMixin, Base):
    """Inspection lots. 01 initial receipt, 09 re-evaluation."""

    __tablename__ = "qals"
    prueflos: Mapped[str] = mapped_column(Text, primary_key=True)  # inspection lot
    art: Mapped[str] = mapped_column(Text)
    matnr: Mapped[str] = mapped_column(Text)
    charg: Mapped[str] = mapped_column(Text)
    pastrterm: Mapped[date] = mapped_column(Date)  # lot start date
    vcode: Mapped[str | None] = mapped_column(String)  # usage decision code
    vdatum: Mapped[date | None] = mapped_column(Date)  # usage decision date
    zresrec: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # LIMS results recorded in ERP
    __table_args__ = (
        ForeignKeyConstraint(["matnr", "charg"], ["mcha.matnr", "mcha.charg"]),
        Index("ix_qals_matnr_charg", "matnr", "charg"),
        CheckConstraint("art in ('01', '09')", name="ck_qals_art"),
    )


class Zinbchk(TimestampMixin, Base):
    """Inbound check per inspection lot."""

    __tablename__ = "zinbchk"
    prueflos: Mapped[str] = mapped_column(ForeignKey("qals.prueflos"), primary_key=True)
    status: Mapped[str] = mapped_column(Text)  # open / passed / resolved / failed (F19)
    completed_on: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str] = mapped_column(Text, default="", server_default="")
    __table_args__ = (
        CheckConstraint("status in ('open', 'passed', 'resolved', 'failed')", name="ck_zinbchk_status"),
    )


INBOUND_OUTCOMES = ("PASS", "FAIL", "PENDING", "NO", "COMP", "APRV", "DCPS")


class ZinbchkItem(TimestampMixin, Base):
    """One sub-check of an inbound check (F19-FR-02)."""

    __tablename__ = "zinbchk_item"
    prueflos: Mapped[str] = mapped_column(ForeignKey("zinbchk.prueflos"), primary_key=True)
    seq: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    check_code: Mapped[str] = mapped_column(Text)
    check_label: Mapped[str] = mapped_column(Text)
    outcome: Mapped[str] = mapped_column(Text)  # PASS FAIL PENDING NO COMP APRV DCPS
    __table_args__ = (
        CheckConstraint(
            "outcome in ('PASS', 'FAIL', 'PENDING', 'NO', 'COMP', 'APRV', 'DCPS')",
            name="ck_zinbchk_item_outcome",
        ),
    )


class Mdez(TimestampMixin, Base):
    """MRP demand."""

    __tablename__ = "mdez"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    matnr: Mapped[str] = mapped_column(ForeignKey("mara.matnr"))
    campaign: Mapped[str] = mapped_column(Text)
    bdter: Mapped[date] = mapped_column(Date)  # requirement date
    bdmng: Mapped[Decimal] = mapped_column(QTY)  # requirement quantity
    is_open: Mapped[bool] = mapped_column(Boolean)
    __table_args__ = (Index("ix_mdez_matnr", "matnr"),)


class Ekpo(TimestampMixin, Base):
    """Purchase-order lines still to be delivered (a pre-batch grain). A goods receipt closes a line."""

    __tablename__ = "ekpo"
    ebeln: Mapped[str] = mapped_column(Text, primary_key=True)  # purchase order, 10 digits starting 45
    ebelp: Mapped[str] = mapped_column(Text, primary_key=True)  # line: 00010, 00020, ...
    matnr: Mapped[str] = mapped_column(ForeignKey("mara.matnr"))
    lifnr: Mapped[str] = mapped_column(ForeignKey("lfa1.lifnr"))
    eindt: Mapped[date] = mapped_column(Date)  # scheduled delivery date
    menge: Mapped[Decimal] = mapped_column(QTY)
    lgort: Mapped[str] = mapped_column(ForeignKey("t001l.lgort"))  # planned receiving location
    is_open: Mapped[bool] = mapped_column(Boolean)
    __table_args__ = (Index("ix_ekpo_matnr", "matnr"),)


class Counter(CounterMixin, Base):
    """Number sequences (documents, lots, demand ids), so a reset restarts numbering."""

    __tablename__ = "counter"
