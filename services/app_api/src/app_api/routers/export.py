"""The CSV exports (F09 AC-10, OQ-062; F18-FR-07, OQ-104).

``/export/table.csv`` is the Overview for the same filters (``/export.csv`` stays as its alias). The Sampling
Plan and the QC Testing Queue use the Overview filters except the stage cards (their stage sets come from the
profile ``exports`` block), and ignore the browser-side column filters and search. Every role may export.
"""

import csv
import dataclasses
import io
from collections.abc import Callable, Sequence
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from r2r_core.profile import SiteProfile
from sqlalchemy.orm import Session

from app_api.auth import current_user
from app_api.db import get_session
from app_api.deps import get_profile
from app_api.routers.overview import overview_filters
from app_api.services.compose import ComposedRow
from app_api.services.overview import FLAG_NAMES, Filters, InvalidFilter, has_flag, select
from app_api.services.store import load_composed

router = APIRouter(dependencies=[Depends(current_user)])

COLUMNS = (
    "row_key", "material_no", "material_desc", "batch_no", "inspection_lot_no", "lot_type", "campaign",
    "stage", "system_need_by_date", "adjusted_need_by_date", "adjusted_reason_code", "operative_need_by",
    "expected_completion", "rag", "days_in_stage", "manual_status", "flags",
)  # fmt: skip
SAMPLING_COLUMNS = (
    "material_no", "material_desc", "batch_no", "lot", "location", "operative_need_by",
    "expected_completion", "days_in_stage", "tags",
)  # fmt: skip
QC_QUEUE_COLUMNS = (
    "material_no", "batch_no", "lot", "sample_id", "offsite", "external_lab", "stage", "stage_entry",
    "expected_completion", "operative_need_by", "tags",
)  # fmt: skip


def tag_labels(row: ComposedRow, profile: SiteProfile) -> str:
    """The row's tags in tag row order, joined with a bar (mirrors frontend/src/lib/tags.ts)."""
    facts = row.facts
    present = (
        ("LATE", row.plan.late),
        ("ON HOLD", row.on_hold_display),
        ("REJECTED", bool(facts["ud_rejected"] or facts["lims_rejected"])),
        ("RE-EVAL", bool(facts["re_eval"])),
        ("EXPEDITE", row.expedite),
        ("FULL SPEC", bool(facts["full_spec"])),
        ("OFFSITE TEST", bool(facts["offsite"])),
        ("RELEASE ON COA", row.coa_release is not None),
        (profile.terms.erp_blocked_tag, bool(facts["erp_blocked"])),
        ("AIR GAP", row.air_gap),
        ("RELEASED", row.stage_terminal),
    )
    return "|".join(label for label, on in present if on)


def _location(row: ComposedRow) -> str:
    place = row.facts["storage_location"]
    return f"{place} {'3PL' if row.facts['location_type'] == '3pl' else 'Onsite'}" if place else ""


def _csv(header: Sequence[str], lines: Sequence[Sequence[object]], filename: str) -> Response:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(lines)
    return Response(
        content=out.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _rows(
    session: Session, profile: SiteProfile, filters: Filters, stages: Sequence[str] | None = None
) -> list[ComposedRow]:
    composed = load_composed(session, profile)
    try:
        if stages is None:
            return select(composed.rows, filters, composed.today)
        chosen = set(stages)
        kept = select(composed.rows, dataclasses.replace(filters, stages=(), q=None), composed.today)
        return [row for row in kept if row.facts["stage_key"] in chosen]
    except InvalidFilter as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


def _table(filters: Filters, session: Session, profile: SiteProfile) -> Response:
    labels = {stage.key: stage.label for stage in profile.stages}
    lines = []
    for row in _rows(session, profile, filters):
        facts = row.facts
        lines.append(
            [
                row.row_key, facts["material_no"], facts["material_desc"], facts["batch_no"],
                facts["inspection_lot_no"], facts["lot_type"], facts["campaign"],
                labels.get(facts["stage_key"], facts["stage_key"]), facts["system_need_by_locked"],
                row.adjusted.date if row.adjusted else "", row.adjusted.reason_code if row.adjusted else "",
                row.operative_need_by, row.plan.expected_completion,
                row.plan.rag.value if row.plan.rag else "",
                row.plan.days_in_stage,
                row.manual_status["rag"] if row.manual_status else "",
                " ".join(name for name in FLAG_NAMES if has_flag(row, name)),
            ]
        )  # fmt: skip
    return _csv(COLUMNS, lines, "overview.csv")


@router.get("/export/table.csv")
def export_table(
    filters: Annotated[Filters, Depends(overview_filters)],
    session: Annotated[Session, Depends(get_session, scope="function")],
    profile: Annotated[SiteProfile, Depends(get_profile)],
) -> Response:
    return _table(filters, session, profile)


@router.get("/export.csv")
def export_csv(
    filters: Annotated[Filters, Depends(overview_filters)],
    session: Annotated[Session, Depends(get_session, scope="function")],
    profile: Annotated[SiteProfile, Depends(get_profile)],
) -> Response:
    """The F09 path, kept as an alias of ``/export/table.csv``."""
    return _table(filters, session, profile)


@router.get("/export/sampling-plan.csv")
def export_sampling_plan(
    filters: Annotated[Filters, Depends(overview_filters)],
    session: Annotated[Session, Depends(get_session, scope="function")],
    profile: Annotated[SiteProfile, Depends(get_profile)],
) -> Response:
    lines = [
        [
            row.facts["material_no"], row.facts["material_desc"], row.facts["batch_no"],
            row.facts["inspection_lot_no"], _location(row), row.operative_need_by,
            row.plan.expected_completion, row.plan.days_in_stage, tag_labels(row, profile),
        ]
        for row in _rows(session, profile, filters, profile.exports.sampling_plan)
    ]  # fmt: skip
    return _csv(SAMPLING_COLUMNS, lines, "sampling-plan.csv")


@router.get("/export/qc-queue.csv")
def export_qc_queue(
    filters: Annotated[Filters, Depends(overview_filters)],
    session: Annotated[Session, Depends(get_session, scope="function")],
    profile: Annotated[SiteProfile, Depends(get_profile)],
) -> Response:
    labels = {stage.key: stage.label for stage in profile.stages}
    offsite: Callable[[ComposedRow], str] = lambda row: "true" if row.facts["offsite_test"] else "false"  # noqa: E731
    lines = [
        [
            row.facts["material_no"], row.facts["batch_no"], row.facts["inspection_lot_no"],
            row.facts["sample_id"], offsite(row), row.facts["external_lab"],
            labels.get(row.facts["stage_key"], row.facts["stage_key"]),
            row.facts["current_stage_entry_date"], row.plan.expected_completion, row.operative_need_by,
            tag_labels(row, profile),
        ]
        for row in _rows(session, profile, filters, profile.exports.qc_queue)
    ]  # fmt: skip
    return _csv(QC_QUEUE_COLUMNS, lines, "qc-testing-queue.csv")
