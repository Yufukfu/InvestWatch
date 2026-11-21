"""GET /stats/summary and GET /stats/trend (specs/rest-api 'Statistics', design decision 9)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Request
from sqlalchemy import func, select

from ..db.mapping import format_time
from ..db.tables import findings, sources
from ..errors import validation_error
from ..models import STATUSES, Module, RiskLevel
from ..queries import risk_level_expr
from ..thresholds import MODULES

router = APIRouter()
RISK_LEVELS = ("high", "medium", "low")
DEFAULT_RANGE = {"hour": timedelta(hours=24), "day": timedelta(days=14)}
STEP = {"hour": timedelta(hours=1), "day": timedelta(days=1)}
MAX_POINTS = 2000


def _zeroed(keys) -> dict[str, int]:
    return {k: 0 for k in keys}


@router.get("/stats/summary")
async def summary(request: Request):
    svc = request.app.state.services
    risk = risk_level_expr(await svc.thresholds.current())
    by: dict[str, dict[str, int]] = {"module": _zeroed(MODULES), "status": _zeroed(STATUSES), "platform": {},
                                     "risk": _zeroed(RISK_LEVELS)}
    async with svc.engine.connect() as conn:
        for name, column in (("module", findings.c.module), ("status", findings.c.status),
                             ("platform", findings.c.platform), ("risk", risk)):
            rows = await conn.execute(select(column.label("k"), func.count()).group_by(column))
            for key, count in rows:
                by[name][key] = count
        last_scan = (await conn.execute(select(func.max(sources.c.last_run_at)))).scalar_one()
    return {"total": sum(by["module"].values()), "by_module": by["module"], "by_status": by["status"],
            "by_platform": dict(sorted(by["platform"].items())), "by_risk_level": by["risk"],
            "last_scan_at": format_time(last_scan) if last_scan else None}


def _floor(dt: datetime, bucket: str) -> datetime:
    dt = dt.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
    return dt.replace(hour=0) if bucket == "day" else dt


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


@router.get("/stats/trend")
async def trend(request: Request, module: Module | None = None, bucket: Literal["hour", "day"] = "hour",
                risk_level: RiskLevel | None = None, date_from: datetime | None = None,
                date_to: datetime | None = None):
    svc = request.app.state.services
    end = _aware(date_to) if date_to else datetime.now(timezone.utc)
    start = _aware(date_from) if date_from else end - DEFAULT_RANGE[bucket]
    if start > end:
        raise validation_error(["query", "date_from"], "date_from is after date_to")
    first, last = _floor(start, bucket), _floor(end, bucket)
    if (last - first) / STEP[bucket] >= MAX_POINTS:
        raise validation_error(["query", "date_from"], f"range has more than {MAX_POINTS} buckets")

    slot = func.date_trunc(bucket, func.timezone("UTC", findings.c.detected_at)).label("slot")
    conditions = [findings.c.detected_at >= start, findings.c.detected_at <= end]
    if module:
        conditions.append(findings.c.module == module)
    if risk_level:
        conditions.append(risk_level_expr(await svc.thresholds.current()) == risk_level)
    async with svc.engine.connect() as conn:
        rows = await conn.execute(select(slot, findings.c.module, func.count()).where(*conditions)
                                  .group_by(slot, findings.c.module))
        counts = {(s.replace(tzinfo=timezone.utc), m): c for s, m, c in rows}

    points, t = [], first
    while t <= last:
        points.append({"t": format_time(t), **{m: counts.get((t, m), 0) for m in MODULES}})
        t += STEP[bucket]
    return {"bucket": bucket, "points": points}
