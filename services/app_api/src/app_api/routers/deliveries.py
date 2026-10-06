"""``GET /api/expected-deliveries``: open purchase-order lines, a pre-batch grain (F17-FR-04, OQ-094).

Type, class, campaign and period apply. Stage, tags and bookmarks never do: these lines are not batches yet.
A period keeps the lines scheduled on or before its end, so overdue lines roll into every current window
(03 section 5.6).
"""

import datetime as dt
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from r2r_core import clock
from r2r_core.profile import SiteProfile
from sqlalchemy import text
from sqlalchemy.orm import Session

from app_api.auth import current_user
from app_api.db import get_session
from app_api.deps import get_profile
from app_api.routers.overview import overview_filters
from app_api.services.overview import UNKNOWN_CLASS, Filters, InvalidFilter, window

router = APIRouter(dependencies=[Depends(current_user)])


class DeliveryOut(BaseModel):
    ebeln: str
    ebelp: str
    material_no: str | None
    material_desc: str | None
    molecule_type: str | None
    material_class: str | None
    supplier_id: str | None
    supplier_name: str | None
    campaign: str | None
    scheduled_date: dt.date | None
    quantity: float | None
    planned_location: str | None
    planned_location_type: str | None
    overdue: bool | None


class DeliveriesOut(BaseModel):
    count: int
    overdue_count: int
    mode: Literal["snapshot", "due_in_period"]
    rows: list[DeliveryOut]


def _kept(row: dict[str, Any], filters: Filters, end: dt.date | None) -> bool:
    if filters.types and row["molecule_type"] not in filters.types:
        return False
    if filters.classes and (row["material_class"] or UNKNOWN_CLASS) not in filters.classes:
        return False
    if filters.campaigns and row["campaign"] not in filters.campaigns:
        return False
    return end is None or (row["scheduled_date"] is not None and row["scheduled_date"] <= end)


@router.get("/expected-deliveries")
def expected_deliveries(
    filters: Annotated[Filters, Depends(overview_filters)],
    session: Annotated[Session, Depends(get_session, scope="function")],
    profile: Annotated[SiteProfile, Depends(get_profile)],
) -> DeliveriesOut:
    today = clock.now().astimezone(profile.site.tz).date()
    try:
        span = window(filters, today)
    except InvalidFilter as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    records = session.execute(text("SELECT * FROM mirror_expected_deliveries")).mappings()
    kept = [dict(r) for r in records if _kept(dict(r), filters, span[1] if span else None)]
    kept.sort(key=lambda r: (r["scheduled_date"] or dt.date.max, r["ebeln"], r["ebelp"]))
    rows = [
        DeliveryOut.model_validate(
            {**r, "quantity": float(r["quantity"]) if r["quantity"] is not None else None}
        )
        for r in kept
    ]
    return DeliveriesOut(
        count=len(rows),
        overdue_count=sum(1 for r in rows if r.overdue),
        mode="snapshot" if span is None else "due_in_period",
        rows=rows,
    )
