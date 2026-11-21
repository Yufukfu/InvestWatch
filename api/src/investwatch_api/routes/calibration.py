"""GET /calibration?module= : precision/recall per threshold for the calibration panel.

Computed from analyst labels on the module's findings (`confirmed` = positive, `false_positive` = negative,
integration-plan §5). Without labels, the latest run stored in `calibration_points` (analytics eval, gold set)
is returned instead.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from sqlalchemy import select

from ..db.sql import latest_calibration_run
from ..db.tables import findings
from ..models import Module

router = APIRouter()
POINT_FIELDS = ("threshold", "tp", "fp", "fn", "tn", "precision", "recall")
GRID = tuple(round(0.05 * i, 2) for i in range(1, 20))  # 0.05 .. 0.95, as in contracts/mocks/calibration-M*.json
LABELS = {"confirmed": True, "false_positive": False}


def curve(labeled: list[tuple[float, bool]]) -> list[dict]:
    """One point per threshold; `labeled` is (score, is_positive)."""
    points = []
    for t in GRID:
        tp = sum(1 for s, pos in labeled if pos and s >= t)
        fp = sum(1 for s, pos in labeled if not pos and s >= t)
        fn = sum(1 for s, pos in labeled if pos and s < t)
        tn = sum(1 for s, pos in labeled if not pos and s < t)
        precision = tp / (tp + fp) if tp + fp else 1.0  # nothing predicted positive: no false alarms
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        points.append({"threshold": t, "tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": round(precision, 3),
                       "recall": round(recall, 3), "f1": round(f1, 3)})
    return points


@router.get("/calibration")
async def calibration(module: Module, request: Request):
    svc = request.app.state.services
    thresholds = await svc.thresholds.current()
    async with svc.engine.connect() as conn:
        rows = await conn.execute(select(findings.c.score, findings.c.status)
                                  .where(findings.c.module == module, findings.c.status.in_(sorted(LABELS))))
        labeled = [(score, LABELS[status]) for score, status in rows]
        stored = [] if labeled else (await conn.execute(latest_calibration_run(module))).mappings().all()
    if labeled:
        points, samples = curve(labeled), len(labeled)
    else:
        points = []
        for r in stored:
            point = {k: r[k] for k in POINT_FIELDS}
            if r["f1"] is not None:
                point["f1"] = r["f1"]
            points.append(point)
        samples = stored[0]["labeled_samples"] if stored else 0
    return {"module": module, "current_threshold": thresholds[module], "labeled_samples": samples, "points": points}
