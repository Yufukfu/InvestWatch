"""GET / PUT /settings/thresholds (ADR 0305): the API owns Redis key iw:settings:thresholds."""

from __future__ import annotations

from fastapi import APIRouter, Request

from ..models import Thresholds

router = APIRouter()


@router.get("/settings/thresholds")
async def get_thresholds(request: Request):
    return await request.app.state.services.thresholds.current()


@router.put("/settings/thresholds")
async def put_thresholds(body: Thresholds, request: Request):
    return await request.app.state.services.thresholds.replace(body.model_dump())
