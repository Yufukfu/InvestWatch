"""Pipeline wiring of the embedding rescue in the topic gate (analytics-embedding-gate group 2). FakeEmbedder only."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import pytest

from conftest import NOW, make_doc
from investwatch_analytics.config import GateSettings
from investwatch_analytics.embeddings import EmbedOutcome
from investwatch_analytics.gate_embedding import OFF_TOPIC, GateEmbedding
from investwatch_analytics.models import ScrapedDocument
from investwatch_analytics.pipeline import Gate, analyze_document
from investwatch_analytics.preprocessing import preprocess
from investwatch_analytics.registry import Registry
from investwatch_analytics.rules.engine import Catalogue

ROOT = Path(__file__).resolve().parents[1]
SOCIAL = {"source_kind": "third_party", "platform": "instagram", "url": "https://www.instagram.com/p/R2/"}
E_ON, E_OFF = np.eye(2, dtype=np.float32)
SEEDS = {"offer": ["oferta"], OFF_TOPIC: ["mecz"]}
# No dictionary hit, longer than 40 characters, an advisory offer M3 can still judge.
NO_VOCAB_OFFER = "Napisz do mnie prywatnie, pokaze Ci jak z odprawy zrobilam nowe auto w pol roku"
MATCH = "Wczoraj wieczorem na stadionie miejskim odbyl sie mecz, kibice spiewali do konca"
VOCAB = "Zainwestuj w CFD na forex, zyski 20% miesiecznie, kontakt w bio"


class FakeEmbedder:
    model = "bge-m3"

    def __init__(self, docs=None, default=E_OFF, status=None):
        self.docs = docs or {}
        self.default = default
        self.status = status  # documents only: a status instead of a vector
        self.calls: list[str] = []

    def embed(self, text, content_hash):
        self.calls.append(text)
        if text in ("oferta", "mecz"):
            return EmbedOutcome(E_ON if text == "oferta" else E_OFF, "bge-m3", "ok")
        if self.status:
            return EmbedOutcome(None, None, self.status)
        return EmbedOutcome(self.docs.get(text, self.default), "bge-m3", "ok")


def norm(text):
    return preprocess(text).normalized


def gate_with(embedder, warm=True, **settings):
    s = GateSettings(**settings)
    ge = GateEmbedding(embedder, SEEDS, s, retry_s=60)
    if warm:
        ge.warm()
    return Gate.from_settings(s, embedding=ge)


@pytest.fixture(scope="module")
def registry() -> Registry:
    return Registry.from_csv(ROOT / "registry" / "seed.csv")


@pytest.fixture(scope="module")
def gold_registry() -> Registry:
    return Registry.from_csv(ROOT / "eval" / "registry.csv")  # the registry eval/run.py uses


@pytest.fixture(scope="module")
def catalogue() -> Catalogue:
    return Catalogue.load()


def doc(text, **kw) -> ScrapedDocument:
    return ScrapedDocument.model_validate(make_doc(**{**SOCIAL, "text": text, **kw}))


def run(d, registry, catalogue, gate, embedder):
    return analyze_document(d, registry=registry, catalogue=catalogue, now=NOW, gate=gate, embedder=embedder)


def log_text(caplog) -> str:
    return "\n".join(f"{r.getMessage()} {r.__dict__}" for r in caplog.records)


def test_vocabulary_free_offer_rescued_and_routed(registry, catalogue):
    emb = FakeEmbedder(docs={norm(NO_VOCAB_OFFER): E_ON})
    a = run(doc(NO_VOCAB_OFFER), registry, catalogue, gate_with(emb), emb)
    assert a.gate.passed and a.gate.reason == "embedding" and a.gate.path == "embedding"
    assert a.embedding is not None and a.embedding.model == "bge-m3"
    # Embedded once: the gate's vector is reused for model.embedder.
    assert emb.calls.count(norm(NO_VOCAB_OFFER)) == 1
    for f in a.findings:
        assert f.model.embedder == "bge-m3"


def test_off_topic_post_dropped_on_the_embedding_path(registry, catalogue, caplog):
    emb = FakeEmbedder()
    with caplog.at_level(logging.INFO):
        a = run(doc(MATCH), registry, catalogue, gate_with(emb), emb)
    assert not a.gate.passed and a.gate.path == "embedding" and a.findings == []
    line = next(r for r in caplog.records if r.getMessage() == "document skipped")
    assert line.reason == "off_topic" and line.gate_path == "embedding"
    assert isinstance(line.similarity, float) and isinstance(line.margin, float)
    assert "stadionie" not in log_text(caplog)


def test_dictionary_hit_does_not_embed_for_the_gate(registry, catalogue):
    emb = FakeEmbedder(default=E_OFF)
    a = run(doc(VOCAB), registry, catalogue, gate_with(emb), emb)
    assert a.gate.passed and a.gate.path == "dictionary"
    # The one document call is the existing model.embedder call after the gate, not a gate decision.
    assert emb.calls.count(norm(VOCAB)) == 1 and a.gate.margin is None


def test_short_text_not_embedded_for_the_gate(registry, catalogue):
    emb = FakeEmbedder(default=E_ON)
    a = run(doc("Ladna dzis pogoda"), registry, catalogue, gate_with(emb), emb)
    assert not a.gate.passed and a.gate.path == "dictionary" and norm("Ladna dzis pogoda") not in emb.calls


def test_firm_own_unaffected(registry, catalogue):
    emb = FakeEmbedder(default=E_OFF)
    a = run(doc(MATCH, source_kind="firm_own", url="https://example.pl/kontakt"), registry, catalogue,
            gate_with(emb), emb)
    assert a.gate.reason == "bypassed_firm_own" and a.gate.path is None


def test_no_gate_embedding_is_fallback(registry, catalogue):
    a = run(doc(MATCH), registry, catalogue, Gate.from_settings(GateSettings()), None)
    assert not a.gate.passed and a.gate.path == "dictionary_only_fallback" and a.gate.similarity is None


def test_centroids_not_built_in_the_pipeline(registry, catalogue):
    emb = FakeEmbedder(default=E_ON)
    a = run(doc(MATCH), registry, catalogue, gate_with(emb, warm=False), emb)
    assert a.gate.path == "dictionary_only_fallback" and not a.gate.passed
    assert "oferta" not in emb.calls and "mecz" not in emb.calls


def test_failed_vector_is_fallback_and_not_retried(registry, catalogue):
    emb = FakeEmbedder()
    g = gate_with(emb)
    emb.status = "embed_timeout"
    a = run(doc(MATCH), registry, catalogue, g, emb)
    assert a.gate.path == "dictionary_only_fallback" and not a.gate.passed
    assert emb.calls.count(norm(MATCH)) == 1
    assert a.embedding is not None and a.embedding.status == "embed_timeout"  # the worker sees why


def test_gate_embeds_with_the_stored_content_hash(registry, catalogue):
    seen = []

    class Recorder(FakeEmbedder):
        def embed(self, text, content_hash):
            seen.append((text, content_hash))
            return super().embed(text, content_hash)

    emb = Recorder()
    d = doc(MATCH, content_hash="ab" * 32)
    run(d, registry, catalogue, gate_with(emb), emb)
    assert (norm(MATCH), "ab" * 32) in seen


def test_rescued_post_with_failed_status_is_never_rescued(registry, catalogue):
    emb = FakeEmbedder(docs={norm(NO_VOCAB_OFFER): E_ON})
    g = gate_with(emb)
    emb.status = "breaker_open"
    a = run(doc(NO_VOCAB_OFFER), registry, catalogue, g, emb)
    assert not a.gate.passed and a.findings == []


def _gold_positives():
    rows = [json.loads(line) for line in (ROOT / "eval" / "gold.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()]
    return [r for r in rows if any((r["expect"].get(m) or {}).get("label") == "positive" for m in ("M1", "M3"))]


def test_gold_set_has_m1_m3_positives():
    assert len(_gold_positives()) >= 10


@pytest.mark.parametrize("row", _gold_positives(), ids=lambda r: r["id"])
def test_gold_positives_never_dropped_even_by_an_off_topic_embedder(row, gold_registry, catalogue):
    emb = FakeEmbedder(default=E_OFF)  # every document sits on the off_topic centroid
    d = ScrapedDocument.model_validate(row["document"])
    a = run(d, gold_registry, catalogue, gate_with(emb), emb)
    assert a.gate is not None and a.gate.passed, (row["id"], a.gate)
