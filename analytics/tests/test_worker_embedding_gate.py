"""Worker, CLI, counter and compose wiring of the embedding gate (analytics-embedding-gate group 3). No real model."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import fakeredis
import numpy as np
import pytest
import redis

from conftest import make_doc
from llm_stub import Reply
from investwatch_analytics.config import SEED_REGISTRY, GateSettings
from investwatch_analytics.embeddings import EmbedOutcome
from investwatch_analytics.gate import STATS_KEY, GateDecision, count_decision
from investwatch_analytics.gate_embedding import OFF_TOPIC, GateEmbedding
from investwatch_analytics.pipeline import Gate, with_embedding
from investwatch_analytics.registry import Registry
from investwatch_analytics.rules.engine import Catalogue
from investwatch_analytics.testing import InMemoryStore, NoopPublisher
from investwatch_analytics.worker import STREAM, Worker, WorkerConfig

ROOT = Path(__file__).resolve().parents[1]
E_ON, E_OFF = np.eye(2, dtype=np.float32)
SEEDS = {"offer": ["oferta"], OFF_TOPIC: ["mecz"]}
DOC_ID = "44444444-4444-4444-8444-444444444444"
SOCIAL = {"source_kind": "third_party", "platform": "instagram", "url": "https://www.instagram.com/p/W/"}
NO_VOCAB = "Napisz do mnie prywatnie, pokaze Ci jak z odprawy zrobilam nowe auto w pol roku"


class FakeEmbedder:
    model = "bge-m3"

    def __init__(self, down=False, vector=E_ON):
        self.down = down
        self.vector = vector
        self.calls: list[str] = []

    def embed(self, text, content_hash):
        self.calls.append(text)
        if self.down:
            return EmbedOutcome(None, None, "embed_unavailable")
        if text in ("oferta", "mecz"):
            return EmbedOutcome(E_ON if text == "oferta" else E_OFF, "bge-m3", "ok")
        return EmbedOutcome(self.vector, "bge-m3", "ok")


class Clock:
    t = 0.0

    def __call__(self):
        return self.t


@pytest.fixture
def r():
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture(scope="module")
def registry():
    return Registry.from_csv(SEED_REGISTRY)


@pytest.fixture(scope="module")
def catalogue():
    return Catalogue.load()


def gate_for(embedder, clock=None):
    s = GateSettings()
    return Gate.from_settings(s, embedding=GateEmbedding(embedder, SEEDS, s, retry_s=60, clock=clock or Clock()))


def worker(r, store, registry, catalogue, gate, embedder):
    return Worker(r, store, NoopPublisher(), registry=registry, catalogue=catalogue,
                  config=WorkerConfig(consumer="w1", block_ms=10), sleep=lambda s: None, jitter=lambda: 0.0,
                  gate=gate, embedder=embedder)


def add(r, store, text):
    store.put_document_row(make_doc(id=DOC_ID, text=text, **SOCIAL))
    r.xadd(STREAM, {"document_id": DOC_ID, "schema": "v1"})


# ---- counter ----------------------------------------------------------------------------------


@pytest.mark.parametrize("decision,expected", [
    (GateDecision(True, "dictionary", 2, path="dictionary"), {"passed": "1", "path_dictionary": "1"}),
    (GateDecision(False, "off_topic", 0, path="dictionary_only_fallback"),
     {"dropped": "1", "path_dictionary_only_fallback": "1"}),
    (GateDecision(False, "off_topic", 0, path="embedding"), {"dropped": "1", "path_embedding": "1"}),
    (GateDecision(True, "embedding", 0, path="embedding"), {"passed": "1", "path_embedding": "1", "rescued": "1"}),
    (GateDecision(True, "bypassed_firm_own", 0), {"bypassed": "1"}),
    (GateDecision(True, "gate_disabled", 0), {"passed": "1"}),
], ids=["dict-pass", "fallback-drop", "embed-drop", "rescue", "bypass", "disabled"])
def test_counter_fields_with_path(r, decision, expected):
    count_decision(r, decision)
    assert r.hgetall(STATS_KEY) == expected


def test_counter_redis_down_is_not_raised(caplog):
    class Broken:
        def pipeline(self, **kw):
            raise redis.ConnectionError("down")

        def hincrby(self, *a):
            raise redis.ConnectionError("down")

    with caplog.at_level(logging.WARNING):
        count_decision(Broken(), GateDecision(True, "embedding", 0, path="embedding"))
    assert any(getattr(x, "reason", None) == "gate_counter_unavailable" for x in caplog.records)


# ---- with_embedding ---------------------------------------------------------------------------


def test_with_embedding_none_embedder_logs_off_once(caplog):
    with caplog.at_level(logging.INFO):
        g = with_embedding(Gate.from_settings(GateSettings()), None, retry_s=60)
    assert g.embedding is None
    assert [x.reason for x in caplog.records if x.getMessage() == "embedding gate off"] == ["embedder_disabled"]


def test_with_embedding_gate_disabled_builds_nothing():
    g = with_embedding(Gate.from_settings(GateSettings(enabled=False)), FakeEmbedder(), retry_s=60)
    assert g.embedding is None


def test_with_embedding_builds_from_the_shipped_seeds():
    g = with_embedding(Gate.from_settings(GateSettings()), FakeEmbedder(), retry_s=60)
    assert g.embedding is not None and not g.embedding.ready


# ---- worker -----------------------------------------------------------------------------------


def test_worker_warms_before_reading_and_rescues(r, registry, catalogue):
    store = InMemoryStore()
    emb = FakeEmbedder()
    g = gate_for(emb)
    w = worker(r, store, registry, catalogue, g, emb)
    w.ensure_group()
    add(r, store, NO_VOCAB)
    w.run_once()
    assert g.embedding.ready
    stats = r.hgetall(STATS_KEY)
    assert stats["rescued"] == "1" and stats["path_embedding"] == "1" and stats["passed"] == "1"


def test_worker_with_embedder_down_falls_back_and_retries_between_messages(r, registry, catalogue):
    store = InMemoryStore()
    emb = FakeEmbedder(down=True)
    clock = Clock()
    g = gate_for(emb, clock)
    w = worker(r, store, registry, catalogue, g, emb)
    w.ensure_group()
    add(r, store, NO_VOCAB)
    w.run_once()
    assert r.hgetall(STATS_KEY) == {"dropped": "1", "path_dictionary_only_fallback": "1"}
    seed_calls = sum(1 for c in emb.calls if c in ("oferta", "mecz"))
    w.run_once()  # within the cooldown: no new seed attempt
    assert sum(1 for c in emb.calls if c in ("oferta", "mecz")) == seed_calls
    emb.down = False
    clock.t = 61
    w.run_once()  # between messages, after the cooldown: built
    assert g.embedding.ready


def test_worker_never_builds_inside_a_message(r, registry, catalogue, monkeypatch):
    store = InMemoryStore()
    emb = FakeEmbedder()
    g = gate_for(emb)
    w = worker(r, store, registry, catalogue, g, emb)
    store.put_document_row(make_doc(id=DOC_ID, text=NO_VOCAB, **SOCIAL))
    calls = []
    monkeypatch.setattr(g.embedding, "warm", lambda: calls.append("warm") or False)
    w._process("1-0", {"document_id": DOC_ID, "schema": "v1"})
    assert calls == [] and r.hgetall(STATS_KEY)["path_dictionary_only_fallback"] == "1"  # the message ran


def test_worker_without_gate_embedding_runs(r, registry, catalogue):
    store = InMemoryStore()
    w = worker(r, store, registry, catalogue, Gate.from_settings(GateSettings()), None)
    w.ensure_group()
    add(r, store, NO_VOCAB)
    w.run_once()
    assert r.hgetall(STATS_KEY) == {"dropped": "1", "path_dictionary_only_fallback": "1"}


# ---- CLI --------------------------------------------------------------------------------------


def write_docs(tmp_path):
    p = tmp_path / "docs.json"
    p.write_text(json.dumps([make_doc(id=DOC_ID, text=NO_VOCAB, **SOCIAL)]), encoding="utf-8")
    return p


def test_cli_warms_and_uses_the_embedding_gate(stub_llm, tmp_path, monkeypatch, capsys):
    from investwatch_analytics import cli as cli_mod

    stub_llm.default = Reply(body=json.dumps({"data": [{"embedding": [1.0] * 8}]}).encode())
    monkeypatch.setenv("EMBED_BASE_URL", stub_llm.base_url)
    monkeypatch.setenv("EMBED_DIM", "8")
    monkeypatch.setenv("REGISTRY_CSV", str(SEED_REGISTRY))
    seen = []
    monkeypatch.setattr(cli_mod, "analyze", lambda d, **kw: seen.append(kw) or [])
    assert cli_mod.main([str(write_docs(tmp_path)), "--no-llm"]) == 0
    capsys.readouterr()
    assert seen[0]["gate"].embedding is not None and seen[0]["gate"].embedding.ready


def test_cli_no_embed_has_no_gate_embedding(tmp_path, monkeypatch, capsys):
    from investwatch_analytics import cli as cli_mod

    monkeypatch.setenv("EMBED_BASE_URL", "http://127.0.0.1:9/v1")
    monkeypatch.setenv("REGISTRY_CSV", str(SEED_REGISTRY))
    seen = []
    monkeypatch.setattr(cli_mod, "analyze", lambda d, **kw: seen.append(kw) or [])
    assert cli_mod.main([str(write_docs(tmp_path)), "--no-llm", "--no-embed"]) == 0
    capsys.readouterr()
    assert seen[0]["gate"].embedding is None


# ---- compose ----------------------------------------------------------------------------------


def test_compose_forwards_every_gate_setting():
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    forwarded = set(re.findall(r"^\s+(GATE_[A-Z_]+): \$\{\1:-\}$", compose, re.M))
    read = set(re.findall(r'"(GATE_[A-Z_]+)"', (ROOT / "src/investwatch_analytics/config.py").read_text("utf-8")))
    assert read and read == forwarded
    assert "GATE_SIM_THRESHOLD" not in compose
