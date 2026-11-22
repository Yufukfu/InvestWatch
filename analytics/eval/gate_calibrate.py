"""Calibrate `GATE_EMBED_MIN_MARGIN` against a real embedder (analytics-embedding-gate, design §4). Run by hand:

    EMBED_BASE_URL=http://127.0.0.1:11434/v1 python analytics/eval/gate_calibrate.py

stdout: a JSON report (per-margin precision/recall on the no-hit lines of `gate_check.jsonl`, every line's
figures, and the gate decision on every gated gold-set document); stderr: JSON logs. Never run in CI or tests.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from investwatch_analytics.config import EmbedSettings, GateSettings  # noqa: E402
from investwatch_analytics.gate import evaluate, load_terms  # noqa: E402
from investwatch_analytics.gate_embedding import GateEmbedding  # noqa: E402
from investwatch_analytics.preprocessing import preprocess  # noqa: E402

EVAL_DIR = Path(__file__).resolve().parent
CANDIDATES = [round(x * 0.01, 2) for x in range(0, 11)]


def _rate(num: int, den: int, empty: float) -> float:
    return round(num / den, 3) if den else empty


def sweep(rows: list[dict[str, Any]], candidates: list[float] = CANDIDATES) -> list[dict[str, Any]]:
    """Precision/recall of `margin >= m` over the no-hit lines (`margin` set), `on_topic` as the positive class."""
    scored = [r for r in rows if r.get("margin") is not None]
    out = []
    for m in candidates:
        tp = sum(1 for r in scored if r["margin"] >= m and r["label"] == "on_topic")
        fp = sum(1 for r in scored if r["margin"] >= m and r["label"] != "on_topic")
        fn = sum(1 for r in scored if r["margin"] < m and r["label"] == "on_topic")
        out.append({"margin": m, "precision": _rate(tp, tp + fp, 1.0), "recall": _rate(tp, tp + fn, 0.0),
                    "tp": tp, "fp": fp, "fn": fn})
    return out


def score_lines(lines: list[dict[str, Any]], ge: GateEmbedding, terms, settings: GateSettings) -> list[dict]:
    rows = []
    for line in lines:
        text = preprocess(line["text"]).normalized
        d = evaluate(text, source_kind="third_party", firm_matched=False, terms=terms, settings=settings)
        row = {"id": line["id"], "label": line["label"], "dict_hits": d.dict_hits, "similarity": None, "margin": None}
        if not d.dict_hits:
            r = ge.rescue(text, None)
            row.update(similarity=r.similarity, margin=r.margin, path=r.path)
        rows.append(row)
    return rows


def main() -> int:
    embed = EmbedSettings.from_env()
    if not embed.enabled:
        sys.stderr.write("EMBED_BASE_URL is not set\n")
        return 2
    from investwatch_analytics.embeddings import build_embedder

    settings = GateSettings.from_env()
    terms = load_terms()
    embedder = build_embedder(embed)
    ge = GateEmbedding(embedder, terms.centroids, settings, retry_s=0)
    started = time.monotonic()
    if not ge.warm():
        sys.stderr.write("centroids could not be built (embedder down?)\n")
        return 1
    warm_s = round(time.monotonic() - started, 2)
    lines = [json.loads(x) for x in (EVAL_DIR / "gate_check.jsonl").read_text(encoding="utf-8").splitlines() if x]
    started = time.monotonic()
    rows = score_lines(lines, ge, terms, settings)
    per_line_s = round((time.monotonic() - started) / max(1, sum(r["margin"] is not None for r in rows)), 3)
    gold = []
    for g in (json.loads(x) for x in (EVAL_DIR / "gold.jsonl").read_text(encoding="utf-8").splitlines() if x):
        doc = g["document"]
        if doc["source_kind"] == "firm_own":
            continue
        text = preprocess(doc["text"]).normalized
        d = evaluate(text, source_kind=doc["source_kind"], firm_matched=False, terms=terms, settings=settings)
        positive = any((g["expect"].get(m) or {}).get("label") == "positive" for m in ("M1", "M3"))
        entry = {"id": g["id"], "m1_m3_positive": positive, "dict_hits": d.dict_hits, "margin": None}
        if not d.dict_hits:
            entry["margin"] = ge.rescue(text, None).margin
        gold.append(entry)
    report = {"model": embed.model, "centroid_build_s": warm_s, "seconds_per_line": per_line_s,
              "current_margin": settings.embed_min_margin, "sweep": sweep(rows), "lines": rows, "gold_gated": gold}
    sys.stdout.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
