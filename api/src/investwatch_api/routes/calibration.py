"""GET /calibration?module= : the latest stored calibration run (written by analytics eval) plus the threshold."""

from __future__ import annotations

from fastapi import APIRouter, Request

from ..db.sql import latest_calibration_run
from ..models import Module

router = APIRouter()
POINT_FIELDS = ("threshold", "tp", "fp", "fn", "tn", "precision", "recall")


@router.get("/calibration")
async def calibration(module: Module, request: Request):
    svc = request.app.state.services
    thresholds = await svc.thresholds.current()
    async with svc.engine.connect() as conn:
        rows = (await conn.execute(latest_calibration_run(module))).mappings().all()
    points = []
    for r in rows:
        point = {k: r[k] for k in POINT_FIELDS}
        if r["f1"] is not None:
            point["f1"] = r["f1"]
        points.append(point)
    return {"module": module, "current_threshold": thresholds[module],
            "labeled_samples": rows[0]["labeled_samples"] if rows else 0, "points": points}
