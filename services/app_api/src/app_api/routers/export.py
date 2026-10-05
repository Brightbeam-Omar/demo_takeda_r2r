"""``GET /api/export.csv``: the Overview rows for the same filters (F09 endpoint table, AC-10, OQ-062).

The system and the adjusted need-by dates are separate columns. Every role may export.
"""

import csv
import io
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from r2r_core.profile import SiteProfile
from sqlalchemy.orm import Session

from app_api.auth import current_user
from app_api.db import get_session
from app_api.deps import get_profile
from app_api.routers.overview import overview_filters
from app_api.services.overview import FLAG_NAMES, Filters, InvalidFilter, has_flag, select
from app_api.services.store import load_composed

router = APIRouter(dependencies=[Depends(current_user)])

COLUMNS = (
    "row_key", "material_no", "material_desc", "batch_no", "inspection_lot_no", "lot_type", "campaign",
    "stage", "system_need_by_date", "adjusted_need_by_date", "adjusted_reason_code", "operative_need_by",
    "expected_completion", "rag", "days_in_stage", "manual_status", "flags",
)  # fmt: skip


@router.get("/export.csv")
def export_csv(
    filters: Annotated[Filters, Depends(overview_filters)],
    session: Annotated[Session, Depends(get_session, scope="function")],
    profile: Annotated[SiteProfile, Depends(get_profile)],
) -> Response:
    composed = load_composed(session, profile)
    try:
        rows = select(composed.rows, filters, composed.today)
    except InvalidFilter as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    labels = {stage.key: stage.label for stage in profile.stages}
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(COLUMNS)
    for row in rows:
        facts = row.facts
        writer.writerow(
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
    return Response(
        content=out.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="overview.csv"'},
    )
