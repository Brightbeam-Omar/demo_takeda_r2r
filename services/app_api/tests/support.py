"""Shared test helpers: a fake contract reader and a complete synthetic published contract."""

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from app_api import models
from app_api.models import MIRRORS, SyncEvent
from r2r_core.contract import ContractUnavailable, PipelineStatus
from sqlalchemy.orm import Session, sessionmaker

STAMP = datetime(2026, 10, 12, 7, 0, tzinfo=UTC)


def _value(kind: Any, column: str, index: int) -> Any:
    if kind is models.TEXT:
        return f"{column}-{index}"
    if kind is models.DATE:
        return date(2026, 10, 1 + index)
    if kind is models.TIMESTAMP:
        return STAMP
    if kind is models.INTEGER:
        return index
    if kind is models.BOOLEAN:
        return index % 2 == 0
    if kind is models.JSON:
        return json.dumps({"n": index})
    return Decimal("90.5")  # the one Numeric column (pct)


def published(
    run_id: str, size: int = 3, **overrides: list[dict[str, Any]]
) -> dict[str, list[dict[str, Any]]]:
    """A complete, consistent published contract of ``size`` rows per object (one status row)."""
    data: dict[str, list[dict[str, Any]]] = {}
    for name, (_, columns, _, _) in MIRRORS.items():
        count = 1 if name == "pipeline_status_v" else size
        data[name] = [
            {
                column: run_id if column in ("run_id", "last_run_id") else _value(kind, column, index)
                for column, kind in columns
            }
            for index in range(count)
        ]
    data["deviations_v"] = []  # an empty object is consistent
    data.update(overrides)
    return data


class FakeReader:
    def __init__(self, data: dict[str, list[dict[str, Any]]]) -> None:
        self.data = data
        self.status_run_ids: list[str] | None = None  # per call of status(); the last one repeats
        self.status_calls = 0
        self.unavailable = False

    def read(self, object_name: str) -> list[dict[str, Any]]:
        if self.unavailable:
            raise ContractUnavailable(f"no published data yet: {object_name} does not exist")
        return self.data[object_name]

    def status(self) -> PipelineStatus:
        if self.unavailable:
            raise ContractUnavailable("no published data yet: pipeline_status_v is empty")
        run_id = self.data["pipeline_status_v"][0]["last_run_id"]
        if self.status_run_ids:
            run_id = self.status_run_ids[min(self.status_calls, len(self.status_run_ids) - 1)]
        self.status_calls += 1
        return PipelineStatus(run_id, STAMP, STAMP, 3, {})


def queue(factory: sessionmaker[Session], run_id: str = "x") -> int:
    with factory() as session:
        event = SyncEvent(source="webhook", run_id=run_id)
        session.add(event)
        session.commit()
        return event.id
