"""GET /documents/{id}/screenshot/{viewport}: the PNG from MinIO. The key comes only from the documents row."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import select

from ..db.tables import documents
from ..errors import ServiceUnavailable
from ..models import Viewport
from ..objectstore import ObjectStoreError

router = APIRouter()


@router.get("/documents/{document_id}/screenshot/{viewport}")
async def screenshot(document_id: UUID, viewport: Viewport, request: Request):
    svc = request.app.state.services
    async with svc.engine.connect() as conn:
        payload = (await conn.execute(select(documents.c.payload).where(documents.c.id == document_id))).scalar()
    key = ((payload or {}).get("screenshots") or {}).get(viewport)
    if not isinstance(key, str) or not key:
        raise HTTPException(404, f"no {viewport} screenshot for document {document_id}")
    try:
        data = await svc.objects.get(key)
    except ObjectStoreError:
        raise ServiceUnavailable("minio") from None
    if data is None:
        raise HTTPException(404, f"no {viewport} screenshot for document {document_id}")
    return Response(data, media_type="image/png")
