"""Replays events through the F04 event functions, in-process, with the demo clock fixed per event.

Every event is one transaction on its own database, exactly as the HTTP endpoints do it, so ``updated_at``
carries the simulated moment of the event. Master data (materials, suppliers, locations) has no event
function in F04 and is written with the models directly, once, before the first event.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from erp_sim import events as erp_events
from erp_sim import schemas as erp_schemas
from erp_sim.db import dsn as erp_dsn
from erp_sim.models import Base as ErpBase
from erp_sim.models import Lfa1, Mara, T001l
from lims_sim import events as lims_events
from lims_sim import schemas as lims_schemas
from lims_sim.db import dsn as lims_dsn
from lims_sim.models import Base as LimsBase
from pydantic import BaseModel
from qms_sim import events as qms_events
from qms_sim import schemas as qms_schemas
from qms_sim.db import dsn as qms_dsn
from qms_sim.models import Base as QmsBase
from r2r_core import clock
from r2r_core.clock import FixedClock
from r2r_core.db import make_engine, make_session_factory
from sqlalchemy import Engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from datagen.events import Event
from datagen.world import World

SECONDS_BETWEEN_EVENTS = 4
FIRST_EVENT_HOUR_UTC = 6  # 07:00 in Dublin in summer, so the local date equals the event day

EventFunction = Any
HANDLERS: dict[tuple[str, str], tuple[type[BaseModel], EventFunction]] = {
    ("erp", "goods_receipt"): (erp_schemas.GoodsReceiptIn, erp_events.goods_receipt),
    ("erp", "goods_receipt_reversal"): (erp_schemas.ReversalIn, erp_events.goods_receipt_reversal),
    ("erp", "transfer"): (erp_schemas.TransferIn, erp_events.transfer),
    ("erp", "inbound_check"): (erp_schemas.InboundCheckIn, erp_events.inbound_check),
    ("erp", "usage_decision"): (erp_schemas.UsageDecisionIn, erp_events.usage_decision),
    ("erp", "reeval_lot"): (erp_schemas.ReevalLotIn, erp_events.reeval_lot),
    ("erp", "results_recorded"): (erp_schemas.ResultsRecordedIn, erp_events.results_recorded),
    ("erp", "stock_block"): (erp_schemas.StockMoveIn, erp_events.stock_block),
    ("erp", "stock_unblock"): (erp_schemas.StockMoveIn, erp_events.stock_unblock),
    ("erp", "hold"): (erp_schemas.HoldIn, erp_events.hold),
    ("erp", "demand"): (erp_schemas.DemandIn, erp_events.demand),
    ("lims", "sample_collected"): (lims_schemas.SampleCollectedIn, lims_events.sample_collected),
    ("lims", "sample_shipped"): (lims_schemas.SampleShippedIn, lims_events.sample_shipped),
    ("lims", "testing_started"): (lims_schemas.SampleRef, lims_events.testing_started),
    ("lims", "approved"): (lims_schemas.SampleRef, lims_events.approved),
    ("lims", "rejected"): (lims_schemas.SampleRef, lims_events.rejected),
    ("lims", "test_result_recorded"): (lims_schemas.TestResultIn, lims_events.test_result_recorded),
    ("qms", "deviation_opened"): (qms_schemas.DeviationOpenedIn, qms_events.deviation_opened),
    ("qms", "deviation_closed"): (qms_schemas.DeviationClosedIn, qms_events.deviation_closed),
}

# Where the key of a created row sits in an event function's result.
CAPTURES: dict[tuple[str, str], tuple[str, str]] = {
    ("erp", "goods_receipt"): ("qals", "prueflos"),
    ("erp", "reeval_lot"): ("qals", "prueflos"),
    ("erp", "demand"): ("mdez", "id"),
    ("lims", "sample_collected"): ("sample", "sample_id"),
    ("qms", "deviation_opened"): ("deviation", "deviation_no"),
}


@dataclass(frozen=True)
class Databases:
    erp: str
    lims: str
    qms: str

    @staticmethod
    def from_env() -> "Databases":
        return Databases(erp_dsn(), lims_dsn(), qms_dsn())


@dataclass
class ExecutionResult:
    keys: dict[str, Any]  # every captured key: "@lot:RM10001|B1001|01" -> "10000042"
    event_count: int
    per_kind: dict[str, int]

    def lot_number(self, ref: str) -> str:
        return str(self.keys[f"@lot:{ref}"])


class Executor:
    def __init__(self, databases: Databases) -> None:
        self.engines: dict[str, Engine] = {
            "erp": make_engine(databases.erp),
            "lims": make_engine(databases.lims),
            "qms": make_engine(databases.qms),
        }
        self.factories: dict[str, sessionmaker[Session]] = {
            name: make_session_factory(engine) for name, engine in self.engines.items()
        }

    def close(self) -> None:
        for engine in self.engines.values():
            engine.dispose()

    def wipe(self) -> None:
        """Empty every table of the three source databases, counters included. ``app`` is never touched."""
        bases: dict[str, type[DeclarativeBase]] = {"erp": ErpBase, "lims": LimsBase, "qms": QmsBase}
        for name, base in bases.items():
            with self.engines[name].begin() as connection:
                tables = ", ".join(table.name for table in base.metadata.sorted_tables)
                connection.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))

    def seed_master_data(self, world: World, at: datetime) -> None:
        clock.set_clock_source(FixedClock(at))
        try:
            with self.factories["erp"]() as session:
                session.add_all(
                    Mara(matnr=m.matnr, maktx=m.description, mtart=m.mtart, zmolty=m.molecule, zclass=m.klass)
                    for m in world.materials
                )
                session.add_all(Lfa1(lifnr=s.lifnr, name1=s.name, land1=s.country) for s in world.suppliers)
                session.add_all(
                    T001l(lgort=loc.lgort, lgobe=loc.name, zloctype=loc.loctype) for loc in world.locations
                )
                session.commit()
        finally:
            clock.set_clock_source(None)

    def replay(self, events: list[Event]) -> ExecutionResult:
        keys: dict[str, Any] = {}
        per_kind: dict[str, int] = defaultdict(int)
        in_day: dict[Any, int] = defaultdict(int)
        try:
            for event in events:
                if event.at is None:
                    index = in_day[event.day]
                    in_day[event.day] += 1
                    start = datetime(
                        event.day.year, event.day.month, event.day.day, FIRST_EVENT_HOUR_UTC, tzinfo=UTC
                    )
                    at = start + timedelta(seconds=SECONDS_BETWEEN_EVENTS * index)
                else:
                    at = event.at
                clock.set_clock_source(FixedClock(at))
                body_type, function = HANDLERS[(event.system, event.kind)]
                body = body_type.model_validate(_resolve(event.body, keys))
                with self.factories[event.system]() as session:
                    result = function(session, body)
                    session.commit()
                if event.capture is not None:
                    table, column = CAPTURES[(event.system, event.kind)]
                    keys[event.capture] = result[table][column]
                per_kind[f"{event.system}.{event.kind}"] += 1
        finally:
            clock.set_clock_source(None)
        return ExecutionResult(keys, len(events), dict(per_kind))


def _resolve(body: dict[str, Any], keys: dict[str, Any]) -> dict[str, Any]:
    """Replace ``@name`` references with the keys the database allocated."""
    out: dict[str, Any] = {}
    for field, value in body.items():
        if isinstance(value, str) and value.startswith("@"):
            if value not in keys:
                raise KeyError(f"event refers to {value} before it was created")
            out[field] = keys[value]
        else:
            out[field] = value
    return out
