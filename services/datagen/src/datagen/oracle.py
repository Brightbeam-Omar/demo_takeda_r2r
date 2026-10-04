"""The sidecar oracle ``expected_stages.csv`` (F05-FR-11): what stage each lot is meant to be in.

It is written next to the report and is never loaded into a source database. F06 uses it to check the stage
engine, and the report computes its distribution from it.
"""

import csv
from pathlib import Path

from datagen.executor import ExecutionResult
from datagen.model import Plan

HEADER = ("row_key", "intended_stage", "story_id")


def oracle_rows(plan: Plan, keys: ExecutionResult | None) -> list[tuple[str, str, str]]:
    """``(row_key, intended_stage, story_id)`` per lot. Without database numbers the lot ref stands in."""
    rows: list[tuple[str, str, str]] = []
    for batch, lot in plan.lots():
        number = keys.lot_number(lot.ref) if keys is not None else lot.ref.split("|", 2)[2]
        rows.append((f"{batch.matnr}|{batch.charg}|{number}", lot.stage, lot.story_id or ""))
    return sorted(rows)


def write_oracle(path: Path, rows: list[tuple[str, str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(HEADER)
        writer.writerows(rows)
