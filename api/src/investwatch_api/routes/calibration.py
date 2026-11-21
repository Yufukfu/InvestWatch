"""GET /calibration?module= : precision/recall per threshold for the calibration panel.

Analyst labels on the module's findings (`confirmed` = positive, `false_positive` = negative, integration-plan
§5) plus the latest run stored in `calibration_points` (analytics gold-set evaluation, ADR 0312): their counts are
summed per threshold and the ratios recomputed, so one or two labels never replace the gold curve. With only one
source, that source is returned as it is.
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


def curve(labeled: list[tuple[float, bool]], base: dict[float, tuple[int, int, int, int]] | None = None) -> list[dict]:
    """One point per threshold; `labeled` is (score, is_positive); `base` adds stored (tp, fp, fn, tn) per threshold."""
    base = base or {}
    points = []
    for t in GRID:
        btp, bfp, bfn, btn = base.get(t, (0, 0, 0, 0))
        tp = btp + sum(1 for s, pos in labeled if pos and s >= t)
        fp = bfp + sum(1 for s, pos in labeled if not pos and s >= t)
        fn = bfn + sum(1 for s, pos in labeled if pos and s < t)
        tn = btn + sum(1 for s, pos in labeled if not pos and s < t)
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
        stored = (await conn.execute(latest_calibration_run(module))).mappings().all()
    if labeled:
        # Keyed by threshold: curve() reads only grid thresholds, so a stored point off the grid is ignored.
        base = {r["threshold"]: (r["tp"], r["fp"], r["fn"], r["tn"]) for r in stored}
        points = curve(labeled, base)
        samples = len(labeled) + (stored[0]["labeled_samples"] if stored else 0)
    else:
        points = []
        for r in stored:
            point = {k: r[k] for k in POINT_FIELDS}
            if r["f1"] is not None:
                point["f1"] = r["f1"]
            points.append(point)
        samples = stored[0]["labeled_samples"] if stored else 0
    return {"module": module, "current_threshold": thresholds[module], "labeled_samples": samples, "points": points}
