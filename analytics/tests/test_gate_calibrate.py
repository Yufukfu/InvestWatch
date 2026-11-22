"""Gate calibration set and sweep (analytics-embedding-gate group 4). The real run is manual; no model here."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np

from investwatch_analytics.config import GateSettings
from investwatch_analytics.embeddings import EmbedOutcome
from investwatch_analytics.gate import load_terms
from investwatch_analytics.gate_embedding import OFF_TOPIC, GateEmbedding

EVAL = Path(__file__).resolve().parents[1] / "eval"
spec = importlib.util.spec_from_file_location("gate_calibrate", EVAL / "gate_calibrate.py")
gate_calibrate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate_calibrate)


def lines():
    return [json.loads(x) for x in (EVAL / "gate_check.jsonl").read_text(encoding="utf-8").splitlines() if x]


def test_check_set_is_labelled_unique_and_disjoint_from_the_seeds():
    rows = lines()
    assert {r["label"] for r in rows} == {"on_topic", "off_topic"}
    assert sum(r["label"] == "on_topic" for r in rows) >= 10 and sum(r["label"] == "off_topic" for r in rows) >= 10
    ids, texts = [r["id"] for r in rows], [r["text"] for r in rows]
    assert len(set(ids)) == len(ids) and len(set(texts)) == len(texts)
    seeds = {s for v in load_terms().centroids.values() for s in v}
    assert not seeds & set(texts)


def test_sweep_counts_only_scored_lines_and_is_inclusive():
    rows = [{"label": "on_topic", "margin": 0.03}, {"label": "on_topic", "margin": 0.01},
            {"label": "off_topic", "margin": 0.03}, {"label": "off_topic", "margin": -0.2},
            {"label": "on_topic", "margin": None}]  # passed on the dictionary: not part of the sweep
    by = {s["margin"]: s for s in gate_calibrate.sweep(rows, [0.0, 0.03, 0.06])}
    assert by[0.0] == {"margin": 0.0, "precision": 0.667, "recall": 1.0, "tp": 2, "fp": 1, "fn": 0}
    assert by[0.03]["tp"] == 1 and by[0.03]["fp"] == 1  # 0.03 >= 0.03 counts
    assert by[0.06] == {"margin": 0.06, "precision": 1.0, "recall": 0.0, "tp": 0, "fp": 0, "fn": 2}


def test_score_lines_embeds_only_no_hit_lines():
    class Fake:
        model = "bge-m3"
        calls: list[str] = []

        def embed(self, text, content_hash):
            self.calls.append(text)
            return EmbedOutcome(np.array([1.0, 0.0], dtype=np.float32), "bge-m3", "ok")

    emb = Fake()
    ge = GateEmbedding(emb, {"offer": ["a"], OFF_TOPIC: ["b"]}, GateSettings(), retry_s=0)
    ge.warm()
    rows = gate_calibrate.score_lines([{"id": "1", "label": "on_topic", "text": "Zainwestuj w forex"},
                                       {"id": "2", "label": "off_topic", "text": "Mecz Legii z Lechem"}],
                                      ge, load_terms(), GateSettings())
    assert rows[0]["margin"] is None and rows[0]["dict_hits"] > 0
    assert rows[1]["margin"] is not None and emb.calls.count("Mecz Legii z Lechem") == 1
