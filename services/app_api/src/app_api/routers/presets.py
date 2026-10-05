"""``/api/presets``: a user's saved Overview filters (F16-FR-05, OQ-089).

A preset stores the filter query string, with ``period`` literally (``this_week`` stays relative). A name the
user already has is 409; the UI then asks to replace it and overwrites through ``PUT``. Presets are personal
and not audited.
"""

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field, field_validator
from r2r_core import clock
from sqlalchemy import select
from sqlalchemy.orm import Session

from app_api.auth import current_user
from app_api.db import get_session
from app_api.models import AppUser, FilterPreset

router = APIRouter()

Query = Annotated[str, Field(max_length=2000)]


class PresetIn(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=60)]
    query: Query

    @field_validator("name")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("name must not be blank")
        return value.strip()


class PresetOverwrite(BaseModel):
    query: Query


class PresetOut(BaseModel):
    id: int
    name: str
    query: str
    created_at: dt.datetime


def _mine(session: Session, user: AppUser, preset_id: int) -> FilterPreset:
    preset = session.get(FilterPreset, preset_id)
    if preset is None or preset.user_key != user.user_key:
        raise HTTPException(status_code=404, detail=f"unknown preset {preset_id}")
    return preset


@router.get("/presets")
def list_presets(
    session: Annotated[Session, Depends(get_session, scope="function")],
    user: Annotated[AppUser, Depends(current_user)],
) -> list[PresetOut]:
    found = session.scalars(
        select(FilterPreset).where(FilterPreset.user_key == user.user_key).order_by(FilterPreset.name)
    )
    return [PresetOut.model_validate(preset, from_attributes=True) for preset in found]


@router.post("/presets", status_code=201)
def create_preset(
    body: PresetIn,
    session: Annotated[Session, Depends(get_session, scope="function")],
    user: Annotated[AppUser, Depends(current_user)],
) -> PresetOut:
    taken = session.scalar(
        select(FilterPreset.id).where(FilterPreset.user_key == user.user_key, FilterPreset.name == body.name)
    )
    if taken is not None:
        raise HTTPException(status_code=409, detail=f"you already have a preset named {body.name!r}")
    preset = FilterPreset(user_key=user.user_key, name=body.name, query=body.query, created_at=clock.now())
    session.add(preset)
    session.flush()
    return PresetOut.model_validate(preset, from_attributes=True)


@router.put("/presets/{preset_id}")
def overwrite_preset(
    preset_id: int,
    body: PresetOverwrite,
    session: Annotated[Session, Depends(get_session, scope="function")],
    user: Annotated[AppUser, Depends(current_user)],
) -> PresetOut:
    preset = _mine(session, user, preset_id)
    preset.query = body.query
    session.flush()
    return PresetOut.model_validate(preset, from_attributes=True)


@router.delete("/presets/{preset_id}", status_code=204)
def delete_preset(
    preset_id: int,
    session: Annotated[Session, Depends(get_session, scope="function")],
    user: Annotated[AppUser, Depends(current_user)],
) -> Response:
    session.delete(_mine(session, user, preset_id))
    return Response(status_code=204)
