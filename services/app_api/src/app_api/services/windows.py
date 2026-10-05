"""The lists behind the two Overview banners: adjusted needs-by dates and air-gap insights (F16-FR-06..09).

Both honour every Overview filter except the stage filter, ``bookmarked`` included (OQ-059(5), OQ-087), so
the banner count and the window always agree. Pure over composed rows: no database, no clock.
"""

import datetime as dt
from collections.abc import Mapping, Sequence

from pydantic import BaseModel

from app_api.services.compose import ADJUSTED, ComposedRow

HOURS_PER_DAY = 24


def adjusted_rows(rows: Sequence[ComposedRow]) -> list[ComposedRow]:
    """Non-released rows with a current adjusted need-by, newest override version first (OQ-090)."""
    found = [row for row in rows if row.adjusted is not None and not row.stage_terminal]
    return sorted(found, key=lambda row: (-row.overrides[ADJUSTED].created_at.timestamp(), row.row_key))


def air_gap_rows(rows: Sequence[ComposedRow]) -> list[ComposedRow]:
    """Every air-gap row, worst first. A row under the air-gap threshold is not an air gap (OQ-088)."""
    return sorted((row for row in rows if row.air_gap), key=lambda row: (-row.air_gap_hours, row.row_key))


class AdjustedRowOut(BaseModel):
    row_key: str
    batch_no: str
    material_no: str
    material_desc: str | None
    system_need_by_date: dt.date | None  # the locked system date
    adjusted_date: dt.date
    delta_days: int | None  # adjusted minus system: negative = pulled earlier
    reason_code: str | None
    reason_label: str | None
    set_by: str
    set_at: dt.datetime


class AdjustedOut(BaseModel):
    total: int
    rows: list[AdjustedRowOut]


def build_adjusted(
    rows: Sequence[ComposedRow], reason_labels: Mapping[str, str], display_names: Mapping[str, str]
) -> AdjustedOut:
    entries = []
    for row in adjusted_rows(rows):
        current = row.overrides[ADJUSTED]
        assert row.adjusted is not None
        system = row.facts["system_need_by_locked"]
        entries.append(
            AdjustedRowOut(
                row_key=row.row_key,
                batch_no=row.facts["batch_no"],
                material_no=row.facts["material_no"],
                material_desc=row.facts["material_desc"],
                system_need_by_date=system,
                adjusted_date=row.adjusted.date,
                delta_days=(row.adjusted.date - system).days if system else None,
                reason_code=current.reason_code,
                reason_label=reason_labels.get(current.reason_code or "", current.reason_code),
                set_by=display_names.get(current.author, current.author),
                set_at=current.created_at,
            )
        )
    return AdjustedOut(total=len(entries), rows=entries)


class InsightRowOut(BaseModel):
    row_key: str
    batch_no: str
    material_no: str
    material_desc: str | None
    stage_key: str
    stage_label: str
    air_gap_hours: int
    days_gap: int  # floor(hours / 24)


class InsightsOut(BaseModel):
    total: int
    rows: list[InsightRowOut]


def build_insights(rows: Sequence[ComposedRow], stage_labels: Mapping[str, str]) -> InsightsOut:
    entries = [
        InsightRowOut(
            row_key=row.row_key,
            batch_no=row.facts["batch_no"],
            material_no=row.facts["material_no"],
            material_desc=row.facts["material_desc"],
            stage_key=row.facts["stage_key"],
            stage_label=stage_labels.get(row.facts["stage_key"], row.facts["stage_key"]),
            air_gap_hours=row.air_gap_hours,
            days_gap=row.air_gap_hours // HOURS_PER_DAY,
        )
        for row in air_gap_rows(rows)
    ]
    return InsightsOut(total=len(entries), rows=entries)
