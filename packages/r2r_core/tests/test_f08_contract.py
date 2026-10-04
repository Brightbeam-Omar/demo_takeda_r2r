"""F08-FR-09: the contract reader (Delta implementation, Databricks stub) and ``PipelineStatus``."""

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pyarrow as pa
import pytest
from deltalake import write_deltalake
from r2r_core.contract import (
    ContractReader,
    ContractUnavailable,
    DatabricksContractReader,
    DeltaContractReader,
    PipelineStatus,
)

STARTED = datetime(2026, 10, 12, 6, 55, tzinfo=UTC)
FINISHED = datetime(2026, 10, 12, 7, 0, tzinfo=UTC)


def write(root: Path, name: str, table: pa.Table) -> None:
    write_deltalake(str(root / "published" / name), table)


def write_status(root: Path, run_id: str = "run-1") -> None:
    write(
        root,
        "pipeline_status_v",
        pa.table(
            {
                "last_run_id": [run_id],
                "started_at": pa.array([STARTED], pa.timestamp("us", tz="UTC")),
                "last_success_at": pa.array([FINISHED], pa.timestamp("us", tz="UTC")),
                "row_count": pa.array([803], pa.int64()),
                "source_freshness_json": ['{"erp":{"extracted_at":"2026-10-12T06:56:00+00:00"}}'],
            }
        ),
    )


def test_f08_fr09_delta_reader_returns_plain_python_values(tmp_path: Path) -> None:
    write(
        tmp_path,
        "weekly_metrics_v",
        pa.table(
            {
                "metric_id": ["M3", "M6"],
                "week_start": pa.array([date(2026, 10, 5), date(2026, 10, 5)], pa.date32()),
                "completed": pa.array([10, 0], pa.int64()),
                "pct": pa.array([Decimal("90.5"), None], pa.decimal128(5, 1)),
                "stamp": pa.array([FINISHED, None], pa.timestamp("us", tz="UTC")),
                "flag": [True, False],
            }
        ),
    )
    rows = DeltaContractReader(tmp_path).read("weekly_metrics_v")
    assert rows == [
        {"metric_id": "M3", "week_start": date(2026, 10, 5), "completed": 10, "pct": Decimal("90.5"),
         "stamp": FINISHED, "flag": True},
        {"metric_id": "M6", "week_start": date(2026, 10, 5), "completed": 0, "pct": None, "stamp": None,
         "flag": False},
    ]  # fmt: skip
    assert rows[0]["stamp"].tzinfo is not None


def test_f08_fr09_status_is_a_pipeline_status_with_parsed_freshness(tmp_path: Path) -> None:
    write_status(tmp_path)
    status = DeltaContractReader(tmp_path).status()
    assert status == PipelineStatus(
        last_run_id="run-1",
        started_at=STARTED,
        last_success_at=FINISHED,
        row_count=803,
        source_freshness={"erp": {"extracted_at": "2026-10-12T06:56:00+00:00"}},
    )


def test_f08_fr09_a_missing_object_means_no_published_data_yet(tmp_path: Path) -> None:
    (tmp_path / "published").mkdir()
    reader = DeltaContractReader(tmp_path)
    with pytest.raises(ContractUnavailable, match="no published data yet"):
        reader.read("batch_pipeline_v")
    with pytest.raises(ContractUnavailable, match="no published data yet"):
        reader.status()


def test_f08_fr09_an_empty_status_object_means_no_published_data_yet(tmp_path: Path) -> None:
    write(tmp_path, "pipeline_status_v", pa.table({"last_run_id": pa.array([], pa.string())}))
    with pytest.raises(ContractUnavailable, match="no published data yet"):
        DeltaContractReader(tmp_path).status()


def test_f08_fr09_the_delta_reader_satisfies_the_protocol(tmp_path: Path) -> None:
    reader: ContractReader = DeltaContractReader(tmp_path)
    assert reader is not None


def test_f08_fr09_the_databricks_reader_is_a_documented_stub() -> None:
    reader = DatabricksContractReader()
    with pytest.raises(NotImplementedError, match="Statement Execution API"):
        reader.read("batch_pipeline_v")
    with pytest.raises(NotImplementedError, match="Statement Execution API"):
        reader.status()
    assert DatabricksContractReader.__doc__
