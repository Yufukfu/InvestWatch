"""GET / POST /sources and PATCH /sources/{id}. documents_count is counted on read, never stored."""

from __future__ import annotations

import uuid
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import func, insert, select, update

from ..db.mapping import source_to_contract
from ..db.tables import documents, sources
from ..models import SourceCreate, SourcePatch

router = APIRouter()


def _with_count():
    count = (select(func.count()).select_from(documents).where(documents.c.source_id == sources.c.id)
             .scalar_subquery().label("documents_count"))
    return select(sources, count)


def _view(row) -> dict:
    out = source_to_contract(row)
    out["documents_count"] = row["documents_count"]
    return out


async def _one(conn, source_id: UUID) -> dict:
    row = (await conn.execute(_with_count().where(sources.c.id == source_id))).mappings().first()
    if row is None:
        raise HTTPException(404, f"source {source_id} not found")
    return _view(row)


@router.get("/sources")
async def list_sources(request: Request):
    async with request.app.state.services.engine.connect() as conn:
        rows = (await conn.execute(_with_count().order_by(sources.c.created_at, sources.c.id))).mappings().all()
    return {"items": [_view(r) for r in rows]}


@router.post("/sources", status_code=201)
async def create_source(body: SourceCreate, request: Request):
    values = body.model_dump(mode="json")
    values["id"] = uuid.uuid4()
    async with request.app.state.services.engine.begin() as conn:
        await conn.execute(insert(sources).values(values))
        return await _one(conn, values["id"])


@router.patch("/sources/{source_id}")
async def patch_source(source_id: UUID, body: SourcePatch, request: Request):
    changes = body.model_dump(mode="json", exclude_unset=True)
    async with request.app.state.services.engine.begin() as conn:
        await conn.execute(update(sources).where(sources.c.id == source_id).values(**changes, updated_at=func.now()))
        return await _one(conn, source_id)  # 404 when no such source
