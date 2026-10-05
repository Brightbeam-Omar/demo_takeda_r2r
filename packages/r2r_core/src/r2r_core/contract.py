"""The published contract as the application reads it (02-architecture section 4, F08-FR-09).

``ContractReader`` is the one door to the data product's ``published`` objects. Tier 1 reads Delta tables
from the lakehouse volume (``DeltaContractReader``); Tier 2 reads them through Databricks
(``DatabricksContractReader``, a stub). Only the sync worker uses a reader; no user request may.

Rows are plain Python values: ``date``, tz-aware ``datetime``, ``Decimal``, ``bool``, ``int``, ``str`` and
``None``. The ``*_json`` columns stay strings. ``deltalake`` is imported when a table is first read, so
importing this module does not pull it in (install the ``delta`` extra where a reader is used).
"""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

PUBLISHED_LAYER = "published"


class ContractUnavailable(Exception):
    """The contract cannot be read: an object is missing, or nothing was ever published."""


@dataclass(frozen=True)
class PipelineStatus:
    """The one row of ``pipeline_status_v``: the last successful run."""

    last_run_id: str
    started_at: datetime
    last_success_at: datetime
    row_count: int
    source_freshness: dict[str, Any]


class ContractReader(Protocol):
    def read(self, object_name: str) -> list[dict[str, Any]]:
        """Every row of a published object (for example ``batch_pipeline_v``)."""
        ...

    def status(self) -> PipelineStatus:
        """The status of the last successful run."""
        ...


class DeltaContractReader:
    """Reads ``<lakehouse>/published/<object>`` Delta tables."""

    def __init__(self, lakehouse_path: str | Path) -> None:
        self.lakehouse_path = Path(lakehouse_path)

    def read(self, object_name: str) -> list[dict[str, Any]]:
        from deltalake import DeltaTable

        path = self.lakehouse_path / PUBLISHED_LAYER / object_name
        if not (path / "_delta_log").is_dir():
            raise ContractUnavailable(
                f"no published data yet: {PUBLISHED_LAYER}.{object_name} does not exist"
            )
        rows: list[dict[str, Any]] = DeltaTable(str(path)).to_pyarrow_table().to_pylist()
        return rows

    def status(self) -> PipelineStatus:
        rows = self.read("pipeline_status_v")
        if not rows:
            raise ContractUnavailable("no published data yet: pipeline_status_v is empty")
        row = rows[0]
        return PipelineStatus(
            last_run_id=row["last_run_id"],
            started_at=row["started_at"],
            last_success_at=row["last_success_at"],
            row_count=row["row_count"],
            source_freshness=json.loads(row["source_freshness_json"] or "{}"),
        )


class DatabricksContractReader:
    """Tier 2 port path, not built in Tier 1.

    It will read the same eight objects from Unity Catalog tables through the Databricks SQL Statement
    Execution API and return the same plain Python values, so the sync worker needs no change.
    """

    def read(self, object_name: str) -> list[dict[str, Any]]:
        raise NotImplementedError(
            "Tier 2: read published objects through the Databricks Statement Execution API"
        )

    def status(self) -> PipelineStatus:
        raise NotImplementedError(
            "Tier 2: read pipeline_status_v through the Databricks Statement Execution API"
        )
