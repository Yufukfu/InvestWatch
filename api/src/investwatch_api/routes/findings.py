"""GET /findings, GET /findings/{id}, PATCH /findings/{id} (contracts/openapi.yaml, specs/rest-api)."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, HTTPException, Query, Request
from sqlalchemy import exists, func, or_, select, update

from ..db.mapping import document_to_contract, finding_to_contract, format_time
from ..db.tables import documents, findings
from ..errors import validation_error
from ..models import STATUSES, FindingPatch, Module, RiskLevel
from ..queries import like_pattern, risk_level_expr
from ..rescan import rescan_state

router = APIRouter()
log = logging.getLogger("investwatch_api.findings")
EVENTS_CHANNEL = "iw:events"
PUBLISH_TIMEOUT_S = 1.0
MAX_PAGE = 100_000  # keeps OFFSET far below bigint
TEXT_PARAM = r"^[^\x00]*$"  # Postgres rejects NUL in text
SORTS = {
    "-detected_at": (findings.c.detected_at.desc(), findings.c.id),
    "detected_at": (findings.c.detected_at.asc(), findings.c.id),
    "-score": (findings.c.score.desc(), findings.c.detected_at.desc(), findings.c.id),
    "score": (findings.c.score.asc(), findings.c.detected_at.desc(), findings.c.id),
}


def _view(row) -> dict:
    out = finding_to_contract(row)
    out["risk_level"] = row["risk_level"]
    return out


def _statuses(raw: str | None) -> set[str] | None:
    if raw is None:
        return None
    wanted = {s.strip() for s in raw.split(",") if s.strip()}
    if not wanted:
        raise validation_error(["query", "status"], "status names no status")
    unknown = wanted - set(STATUSES)
    if unknown:
        raise validation_error(["query", "status"], f"unknown status {sorted(unknown)}")
    return wanted


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


@router.get("/findings")
async def list_findings(
    request: Request,
    module: Module | None = None,
    status: str | None = None,
    platform: Annotated[str | None, Query(max_length=32, pattern=TEXT_PARAM)] = None,
    source_id: UUID | None = None,
    document_id: UUID | None = None,
    risk_level: RiskLevel | None = None,
    score_min: Annotated[float | None, Query(ge=0, le=1)] = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    q: Annotated[str | None, Query(max_length=200, pattern=TEXT_PARAM)] = None,
    sort: Annotated[str, Query(pattern="^-?(detected_at|score)$")] = "-detected_at",
    page: Annotated[int, Query(ge=1, le=MAX_PAGE)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
):
    svc = request.app.state.services
    statuses = _statuses(status)
    risk = risk_level_expr(await svc.thresholds.current()).label("risk_level")

    conditions = []
    if module:
        conditions.append(findings.c.module == module)
    if statuses:
        conditions.append(findings.c.status.in_(sorted(statuses)))
    if platform:
        conditions.append(findings.c.platform == platform)
    if source_id:
        conditions.append(exists().where(documents.c.id == findings.c.document_id, documents.c.source_id == source_id))
    if document_id:
        conditions.append(findings.c.document_id == document_id)
    if risk_level:
        conditions.append(risk == risk_level)
    if score_min is not None:
        conditions.append(findings.c.score >= score_min)
    if date_from:
        conditions.append(findings.c.detected_at >= _aware(date_from))
    if date_to:
        conditions.append(findings.c.detected_at <= _aware(date_to))
    if q and q.strip():
        pattern = like_pattern(q.strip())
        fields = (findings.c.title, findings.c.content_excerpt, findings.c.firm["name"].astext,
                  findings.c.advertiser["name"].astext, findings.c.advertiser["handle"].astext)
        conditions.append(or_(*[f.ilike(pattern, escape="\\") for f in fields]))

    async with svc.engine.connect() as conn:
        total = (await conn.execute(select(func.count()).select_from(findings).where(*conditions))).scalar_one()
        rows = (await conn.execute(select(findings, risk).where(*conditions).order_by(*SORTS[sort])
                                   .limit(page_size).offset((page - 1) * page_size))).mappings().all()
    return {"items": [_view(r) for r in rows], "total": total, "page": page, "page_size": page_size}


async def _finding_row(conn, finding_id: UUID, thresholds: dict):
    row = (await conn.execute(select(findings, risk_level_expr(thresholds).label("risk_level"))
                              .where(findings.c.id == finding_id))).mappings().first()
    if row is None:
        raise HTTPException(404, f"finding {finding_id} not found")
    return row


@router.get("/findings/{finding_id}")
async def get_finding(finding_id: UUID, request: Request):
    svc = request.app.state.services
    thresholds = await svc.thresholds.current()
    async with svc.engine.connect() as conn:
        row = await _finding_row(conn, finding_id, thresholds)
        doc = (await conn.execute(select(documents).where(documents.c.id == row["document_id"]))).mappings().first()
        rescan = await rescan_state(conn, doc) if doc else None
    view = _view(row)
    document = document_to_contract(doc) if doc else None
    if document is not None:
        # The contract's only open slot for it (finding.schema.json is closed): scrape_meta.rescan, issue #71.
        document["scrape_meta"] = {**(document.get("scrape_meta") or {}), "rescan": rescan}
    view["document"] = document
    shots = (document or {}).get("screenshots") or {}
    view["screenshot_urls"] = {vp: f"/api/documents/{row['document_id']}/screenshot/{vp}"
                               for vp, key in shots.items() if key}
    return view


async def publish_event(redis, event_type: str, data: dict) -> None:
    """Publish on iw:events after a commit; a failure is logged, never returned (design decision 5)."""
    message = {"type": event_type, "emitted_at": format_time(datetime.now(timezone.utc).replace(microsecond=0)),
               "data": data}
    try:
        await asyncio.wait_for(redis.publish(EVENTS_CHANNEL, json.dumps(message)), PUBLISH_TIMEOUT_S)
    except Exception as exc:
        log.error("event publish failed", extra={"event": event_type, "reason": type(exc).__name__})


@router.patch("/findings/{finding_id}")
async def patch_finding(finding_id: UUID, patch: Annotated[FindingPatch, Body()], request: Request):
    svc = request.app.state.services
    thresholds = await svc.thresholds.current()
    changes = patch.model_dump(exclude_unset=True)
    async with svc.engine.begin() as conn:
        current = await _finding_row(conn, finding_id, thresholds)
        # Strictly later than the previous value, even if a producer wrote a timestamp slightly in the future.
        stamp = max(datetime.now(timezone.utc), current["updated_at"] + timedelta(microseconds=1))
        await conn.execute(update(findings).where(findings.c.id == finding_id).values(**changes, updated_at=stamp))
        row = await _finding_row(conn, finding_id, thresholds)
    await publish_event(svc.redis, "finding.updated", {"id": str(finding_id), "status": row["status"]})
    return _view(row)
