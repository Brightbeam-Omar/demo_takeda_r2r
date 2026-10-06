"""Replace the ``mirror_*`` tables from the published contract (F08-FR-05, FR-05b, FR-10).

``sync_mirror`` runs inside the caller's transaction: it reads every published object, refuses a mixed state,
and then replaces every mirror (twelve) and its watermark row. The caller commits (or rolls everything back).
"""

import json
import logging
import time
from dataclasses import dataclass
from typing import Any

from r2r_core.contract import ContractReader
from sqlalchemy import Table, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app_api.models import JSON, MIRROR_TABLES, MIRRORS, OBJECTS_WITH_RUN_ID, Watermark

log = logging.getLogger(__name__)


class SyncError(Exception):
    """The published contract cannot be mirrored now. The event fails and the mirror stays as it was."""


@dataclass(frozen=True)
class SyncResult:
    rows_upserted: int
    noop: bool


def _ms(began: float) -> float:
    return round((time.perf_counter() - began) * 1000, 1)


def read_published(reader: ContractReader) -> tuple[str, dict[str, list[dict[str, Any]]]]:
    """Every published object and the run they belong to. ``pipeline_status_v`` is read before and after."""
    before = reader.status().last_run_id
    data = {name: reader.read(name) for name in MIRRORS}
    after = reader.status().last_run_id
    if before != after:
        raise SyncError(
            f"publish in progress: pipeline_status_v moved from run {before} to {after} during the read"
        )
    return after, data


def check_consistent(run_id: str, data: dict[str, list[dict[str, Any]]]) -> None:
    """Every row of every object that carries a ``run_id`` must belong to the status's run (F08-FR-10)."""
    status_rows = data["pipeline_status_v"]
    if len(status_rows) != 1 or status_rows[0]["last_run_id"] != run_id:
        raise SyncError(f"pipeline_status_v does not show run {run_id}")
    for name in OBJECTS_WITH_RUN_ID:
        stale = sorted({row["run_id"] for row in data[name]} - {run_id})
        if stale:
            raise SyncError(
                f"mixed publish: {name} holds run {', '.join(stale)} but pipeline_status_v shows run {run_id}"
            )


def _record(name: str, row: dict[str, Any], run_id: str, mirrored_at: Any) -> dict[str, Any]:
    _, columns, _, _ = MIRRORS[name]
    record: dict[str, Any] = {}
    for column, kind in columns:
        if column not in row:
            raise SyncError(f"published object {name} has no column {column}")
        value = row[column]
        record[column] = json.loads(value) if value is not None and kind is JSON else value
    record["contract_run_id"] = run_id
    record["mirrored_at"] = mirrored_at
    return record


def _insert_rows(session: Session, table: Table, records: list[dict[str, Any]]) -> None:
    if records:
        session.execute(table.insert(), records)


def sync_mirror(session: Session, reader: ContractReader) -> SyncResult:
    """Mirror the currently published run, or do nothing when the mirror already holds it."""
    began = time.perf_counter()
    run_id, data = read_published(reader)
    log.info(
        "contract_pulled",
        extra={"run_id": run_id, "rows": sum(map(len, data.values())), "duration_ms": _ms(began)},
    )
    check_consistent(run_id, data)
    held = dict(session.execute(select(Watermark.object_name, Watermark.run_id)).tuples().all())
    if all(held.get(name) == run_id for name in MIRRORS):
        return SyncResult(rows_upserted=0, noop=True)

    began = time.perf_counter()
    now = session.execute(select(func.now())).scalar_one()
    total = 0
    for name, table in MIRROR_TABLES.items():
        records = [_record(name, row, run_id, now) for row in data[name]]
        session.execute(table.delete())  # DELETE, not TRUNCATE: readers keep the old rows until commit
        _insert_rows(session, table, records)
        total += len(records)
        upsert = insert(Watermark).values(object_name=name, run_id=run_id, synced_at=now)
        session.execute(
            upsert.on_conflict_do_update(
                index_elements=[Watermark.object_name], set_={"run_id": run_id, "synced_at": now}
            )
        )
    log.info("mirror_upserted", extra={"run_id": run_id, "rows": total, "duration_ms": _ms(began)})
    return SyncResult(rows_upserted=total, noop=False)
