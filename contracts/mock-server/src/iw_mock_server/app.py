"""ASGI app: FastAPI routes under /api plus Socket.IO namespace /events.

Routes and bodies follow contracts/openapi.yaml; data comes from the in-memory Store.
Routes under /__mock/ are development helpers and not part of the contract.

Every route is `async def` on purpose: FastAPI runs plain `def` routes in a thread pool, and the store
is also written by replay and scans on the event loop. Keeping all access on the single loop thread
means no locks and no "dictionary changed size during iteration".
"""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal, get_args
from uuid import UUID

from fastapi import Body, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import AfterValidator, BaseModel, ConfigDict, Field, HttpUrl, TypeAdapter, model_validator
from starlette.exceptions import HTTPException as StarletteHTTPException

from .png import placeholder_png
from .settings import Settings
from .store import MODULES, Store, load_mock_data

log = logging.getLogger("iw_mock_server")

Module = Literal["M1", "M2", "M3"]
RiskLevel = Literal["high", "medium", "low"]
Viewport = Literal["desktop", "tablet", "mobile"]
Platform = Literal["web", "facebook", "instagram", "tiktok", "youtube", "x", "forum", "other"]
SourceKind = Literal["firm_own", "third_party", "unknown"]
Status = Literal["new", "in_review", "confirmed", "false_positive", "closed"]
STATUSES: tuple[str, ...] = get_args(Status)

_HTTP_URL = TypeAdapter(HttpUrl)


def _http_url(value: str) -> str:
    """Validate like HttpUrl but keep the string as sent: HttpUrl would add a trailing slash and
    lowercase the host, so the source would come back different from what the client stored."""
    _HTTP_URL.validate_python(value)
    return value


def _unique(values: list) -> list:
    if len(set(values)) != len(values):  # source.schema.json: target_modules has uniqueItems
        raise ValueError("items must be unique")
    return values


SourceUrl = Annotated[str, AfterValidator(_http_url)]
TargetModules = Annotated[list[Module], Field(min_length=1), AfterValidator(_unique)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FindingPatch(_Strict):
    status: Status | None = None
    note: str | None = None

    @model_validator(mode="after")
    def _not_empty(self):
        if not self.model_fields_set:
            raise ValueError("at least one of status, note is required")
        return self


class Thresholds(_Strict):
    M1: float = Field(ge=0, le=1)
    M2: float = Field(ge=0, le=1)
    M3: float = Field(ge=0, le=1)


class SourceCreate(_Strict):
    name: str = Field(min_length=1)
    platform: Platform
    url: SourceUrl
    source_kind: SourceKind
    target_modules: TargetModules
    schedule_cron: str | None = None
    active: bool = True


class SourcePatch(_Strict):
    name: str | None = Field(default=None, min_length=1)
    platform: Platform | None = None
    url: SourceUrl | None = None
    source_kind: SourceKind | None = None
    target_modules: TargetModules | None = None
    schedule_cron: str | None = None
    active: bool | None = None

    @model_validator(mode="after")
    def _not_empty(self):
        if not self.model_fields_set:
            raise ValueError("at least one field is required")
        return self


class ScanRequest(_Strict):
    source_id: UUID


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def bumped_timestamp(previous: str | None) -> str:
    """Now, but never earlier than (previous + 1 s): mock timestamps may lie in the future."""
    now = datetime.now(timezone.utc).replace(microsecond=0)
    if previous:
        now = max(now, parse_ts(previous) + timedelta(seconds=1))
    return iso(now)


def parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _matches_text(finding: dict, needle: str) -> bool:
    # openapi.yaml: "Full-text search in title, excerpt, firm and advertiser"
    haystack = [finding.get("title"), finding.get("content_excerpt"),
                (finding.get("firm") or {}).get("name"),
                (finding.get("advertiser") or {}).get("name"), (finding.get("advertiser") or {}).get("handle")]
    return any(needle in h.lower() for h in haystack if h)


def create_app(settings: Settings | None = None, store: Store | None = None) -> FastAPI:
    settings = settings or Settings()
    store = store or Store(load_mock_data(settings.contracts_dir))

    api = FastAPI(title="InvestWatch mock API", version="1.0.0")
    api.state.store = store
    api.state.settings = settings
    api.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_methods=["*"],
                       allow_headers=["*"])

    # --- error bodies in the contract shape { "error": ..., "details": ... } ----------------

    @api.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException):
        return JSONResponse({"error": str(exc.detail)}, status_code=exc.status_code)

    @api.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        details = [{"loc": list(e.get("loc", [])), "msg": e.get("msg")} for e in exc.errors()]
        return JSONResponse({"error": "validation_error", "details": details}, status_code=422)

    def get_finding_or_404(finding_id: UUID) -> dict:
        finding = store.findings.get(str(finding_id))
        if finding is None:
            raise HTTPException(404, f"finding {finding_id} not found")
        return finding

    # --- findings -------------------------------------------------------------------------

    @api.get("/api/findings")
    async def list_findings(
        module: Module | None = None,
        status: str | None = None,
        platform: str | None = None,
        source_id: UUID | None = None,
        risk_level: RiskLevel | None = None,
        score_min: Annotated[float | None, Query(ge=0, le=1)] = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        q: str | None = None,
        sort: Literal["detected_at", "-detected_at", "score", "-score"] = "-detected_at",
        page: Annotated[int, Query(ge=1)] = 1,
        page_size: Annotated[int, Query(ge=1, le=200)] = 50,
    ):
        statuses = None
        if status:
            statuses = {s.strip() for s in status.split(",") if s.strip()}
            unknown = statuses - set(STATUSES)
            if unknown:
                raise RequestValidationError([{"loc": ["query", "status"], "msg": f"unknown status {sorted(unknown)}"}])
        needle = q.lower().strip() if q else None
        docs_of_source = ({d["id"] for d in store.documents.values() if d.get("source_id") == str(source_id)}
                          if source_id else None)

        result = []
        for f in store.findings.values():
            if module and f["module"] != module:
                continue
            if statuses and f["status"] not in statuses:
                continue
            if platform and f["platform"] != platform:
                continue
            if docs_of_source is not None and f["document_id"] not in docs_of_source:
                continue
            if risk_level and store.risk_level_of(f) != risk_level:
                continue
            if score_min is not None and f["score"] < score_min:
                continue
            detected = parse_ts(f["detected_at"])
            if date_from and detected < _aware(date_from):
                continue
            if date_to and detected > _aware(date_to):
                continue
            if needle and not _matches_text(f, needle):
                continue
            result.append(f)

        key = sort.lstrip("-")
        result.sort(key=(lambda f: parse_ts(f["detected_at"])) if key == "detected_at" else (lambda f: f["score"]),
                    reverse=sort.startswith("-"))
        start = (page - 1) * page_size
        return {"items": [store.finding_view(f) for f in result[start:start + page_size]],
                "total": len(result), "page": page, "page_size": page_size}

    @api.get("/api/findings/{finding_id}")
    async def get_finding(finding_id: UUID):
        finding = get_finding_or_404(finding_id)
        view = store.finding_view(finding)
        document = store.documents.get(finding["document_id"])
        view["document"] = document
        shots = (document or {}).get("screenshots") or {}
        view["screenshot_urls"] = {vp: f"/api/documents/{finding['document_id']}/screenshot/{vp}"
                                   for vp, key in shots.items() if key}
        return view

    @api.patch("/api/findings/{finding_id}")
    async def patch_finding(finding_id: UUID, patch: Annotated[FindingPatch, Body()]):
        finding = get_finding_or_404(finding_id)
        for key, value in patch.model_dump(exclude_unset=True).items():
            if key == "status" and value is None:
                raise RequestValidationError([{"loc": ["body", "status"], "msg": "status cannot be null"}])
            finding[key] = value
        finding["updated_at"] = bumped_timestamp(finding.get("updated_at"))
        api.state.notify("finding.updated", {"id": finding["id"], "status": finding["status"]})
        return store.finding_view(finding)

    # --- stats ----------------------------------------------------------------------------

    @api.get("/api/stats/summary")
    async def stats_summary():
        findings = list(store.findings.values())

        def count(key_fn, keys):
            counts = {k: 0 for k in keys}
            for f in findings:
                k = key_fn(f)
                counts[k] = counts.get(k, 0) + 1
            return counts

        last_runs = [s["last_run_at"] for s in store.sources.values() if s.get("last_run_at")]
        return {
            "total": len(findings),
            "by_module": count(lambda f: f["module"], MODULES),
            "by_status": count(lambda f: f["status"], STATUSES),
            "by_platform": count(lambda f: f["platform"], sorted({f["platform"] for f in findings})),
            "by_risk_level": count(store.risk_level_of, ("high", "medium", "low")),
            "last_scan_at": max(last_runs) if last_runs else None,
        }

    @api.get("/api/stats/trend")
    async def stats_trend(
        module: Module | None = None,
        bucket: Literal["hour", "day"] = "hour",
        risk_level: RiskLevel | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ):
        hourly = store.trend_points(risk_level)
        if date_from:
            hourly = [p for p in hourly if parse_ts(p["t"]) >= _aware(date_from)]
        if date_to:
            hourly = [p for p in hourly if parse_ts(p["t"]) <= _aware(date_to)]

        if bucket == "day":
            days: dict[str, dict] = defaultdict(lambda: {m: 0 for m in MODULES})
            for p in hourly:
                day = parse_ts(p["t"]).strftime("%Y-%m-%dT00:00:00Z")
                for m in MODULES:
                    days[day][m] += p[m]
            points = [{"t": t, **counts} for t, counts in sorted(days.items())]
        else:
            points = [dict(p) for p in hourly]

        if module:
            for p in points:
                for m in MODULES:
                    if m != module:
                        p[m] = 0
        return {"bucket": bucket, "points": points}

    # --- calibration and settings ---------------------------------------------------------

    @api.get("/api/calibration")
    async def calibration(module: Module):
        body = dict(store.calibration[module])
        body["current_threshold"] = store.thresholds[module]
        return body

    @api.get("/api/settings/thresholds")
    async def get_thresholds():
        return dict(store.thresholds)

    @api.put("/api/settings/thresholds")
    async def put_thresholds(thresholds: Thresholds):
        store.thresholds.update(thresholds.model_dump())
        return dict(store.thresholds)

    # --- sources, scans, documents, health ------------------------------------------------

    @api.get("/api/sources")
    async def list_sources():
        return {"items": list(store.sources.values())}

    @api.post("/api/sources", status_code=201)
    async def create_source(body: SourceCreate):
        source = body.model_dump(mode="json")
        source.update(id=str(uuid.uuid4()), last_run_at=None, last_run_status=None, documents_count=0)
        store.sources[source["id"]] = source
        return source

    @api.patch("/api/sources/{source_id}")
    async def patch_source(source_id: UUID, patch: SourcePatch):
        source = store.sources.get(str(source_id))
        if source is None:
            raise HTTPException(404, f"source {source_id} not found")
        changes = patch.model_dump(mode="json", exclude_unset=True)
        nulls = [k for k, v in changes.items() if v is None and k != "schedule_cron"]
        if nulls:
            raise RequestValidationError([{"loc": ["body", k], "msg": "cannot be null"} for k in nulls])
        source.update(changes)
        return source

    @api.post("/api/scans", status_code=202)
    async def request_scan(body: ScanRequest):
        source_id = str(body.source_id)
        if source_id not in store.sources:
            raise HTTPException(404, f"source {source_id} not found")
        api.state.start_scan(source_id)
        return {"queued": True, "source_id": source_id}

    @api.get("/api/documents/{document_id}/screenshot/{viewport}")
    async def screenshot(document_id: UUID, viewport: Viewport):
        document = store.documents.get(str(document_id))
        if not document or not (document.get("screenshots") or {}).get(viewport):
            raise HTTPException(404, f"no {viewport} screenshot for document {document_id}")
        return Response(placeholder_png(viewport), media_type="image/png")

    @api.get("/api/health")
    async def health():
        return store.health

    # --- mock-only helpers (not part of the contract) -------------------------------------

    @api.post("/__mock/reset")
    async def mock_reset():
        store.reset()
        return {"reset": True}

    @api.post("/__mock/emit")
    async def mock_emit():
        replay_once = api.state.replay_once
        if replay_once is None:
            raise HTTPException(503, "events are not mounted (use events.create_asgi_app)")
        return replay_once()

    # Event hooks; replaced with Socket.IO emitters when the app is mounted (events.py).
    api.state.notify = lambda event_type, data: None
    api.state.start_scan = lambda source_id: None
    api.state.replay_once = None

    return api
