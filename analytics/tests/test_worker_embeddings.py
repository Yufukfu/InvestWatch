"""Worker, CLI and startup wiring of the gate, embedder and near-dup index (analytics-embeddings group 9, 8b counter)."""

from __future__ import annotations

import json
import logging

import fakeredis
import numpy as np
import pytest
import redis

from conftest import NOW, make_doc
from llm_stub import Reply
from investwatch_analytics.config import (
    SEED_REGISTRY,
    ConfigError,
    GateSettings,
    LlmSettings,
    NearDupSettings,
)
from investwatch_analytics.embeddings import EmbedOutcome
from investwatch_analytics.gate import STATS_KEY, count_decision, evaluate, load_terms
from investwatch_analytics.neardup import NearDupIndex
from investwatch_analytics.pipeline import Gate
from investwatch_analytics.registry import Registry
from investwatch_analytics.rules.engine import Catalogue
from investwatch_analytics.testing import InMemoryStore, NoopPublisher
from investwatch_analytics.worker import STREAM, Worker, WorkerConfig, preprocessing_from_env

ORIG = "11111111-1111-4111-8111-111111111111"
COPY = "22222222-2222-4222-8222-222222222222"
RECIPE_ID = "33333333-3333-4333-8333-333333333333"
SOCIAL = {"source_kind": "third_party", "platform": "instagram", "author": {"handle": "@trader_ola"}}
POST = ("Konto mam w EuroTrade Markets. Moja grupa: co tydzień mówię, co kupić z akcji WIG20. "
        + " ".join(f"Akcja {i} na sesji rośnie o {i} procent." for i in range(40)))
VEC = np.ones(8, dtype=np.float32) / np.sqrt(8)


@pytest.fixture(scope="module")
def registry():
    return Registry.from_csv(SEED_REGISTRY)


@pytest.fixture(scope="module")
def catalogue():
    return Catalogue.load()


@pytest.fixture
def r():
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def store():
    s = InMemoryStore()
    s.put_document_row(make_doc(id=ORIG, url="https://www.instagram.com/p/A/", text=POST, **SOCIAL))
    s.put_document_row(make_doc(id=COPY, url="https://www.instagram.com/p/B/", text=POST + " 🚀", **SOCIAL))
    s.put_document_row(make_doc(id=RECIPE_ID, url="https://www.instagram.com/p/C/",
                                text="Przepis na sernik babci: twaróg, jajka, cukier i masło.", **SOCIAL))
    return s


class GroupRecorder(NoopPublisher):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.calls = []

    def publish_findings(self, saved, groups=None):
        self.calls.append(groups)
        return super().publish_findings(saved, groups=groups)


class FakeEmbedder:
    model = "bge-m3"

    def embed(self, text, content_hash):
        return EmbedOutcome(VEC, "bge-m3", "ok")


def make_worker(r, store, registry, catalogue, publisher, **kw):
    config = WorkerConfig(consumer="w1", block_ms=10)
    return Worker(r, store, publisher, registry=registry, catalogue=catalogue, config=config, now=lambda: NOW,
                  sleep=lambda s: None, jitter=lambda: 0.0, **kw)


def handle(w, r, *ids):
    w.ensure_group()
    for d in ids:
        r.xadd(STREAM, {"document_id": d, "schema": "v1"})
    while w.run_once():
        pass


GATE = Gate.from_settings(GateSettings())


# ---- gate counter -----------------------------------------------------------------------------


@pytest.mark.parametrize("text,kind,field", [("zysk", "third_party", "passed"), ("sernik", "third_party", "dropped"),
                                             ("sernik", "firm_own", "bypassed")])
def test_counter_fields(r, text, kind, field):
    d = evaluate(text, source_kind=kind, firm_matched=False, terms=load_terms(), settings=GateSettings())
    count_decision(r, d)
    assert r.hgetall(STATS_KEY) == {field: "1"}


def test_counter_disabled_gate_counts_as_passed(r):
    d = evaluate("sernik", source_kind="third_party", firm_matched=False, terms=load_terms(),
                 settings=GateSettings(enabled=False))
    count_decision(r, d)
    assert r.hgetall(STATS_KEY) == {"passed": "1"}


def test_counter_redis_down_is_logged_not_raised(caplog):
    class Broken:
        def hincrby(self, *a):
            raise redis.ConnectionError("down")

    d = evaluate("zysk", source_kind="third_party", firm_matched=False, terms=load_terms(), settings=GateSettings())
    with caplog.at_level(logging.WARNING):
        count_decision(Broken(), d)
    assert any(getattr(x, "reason", None) == "gate_counter_unavailable" for x in caplog.records)


# ---- worker -----------------------------------------------------------------------------------


def test_worker_drops_off_topic_and_counts(r, store, registry, catalogue, caplog):
    pub = GroupRecorder()
    w = make_worker(r, store, registry, catalogue, pub, gate=GATE)
    with caplog.at_level(logging.INFO):
        handle(w, r, RECIPE_ID, ORIG)
    assert r.hgetall(STATS_KEY) == {"dropped": "1", "passed": "1"}
    assert store.findings_for_document(RECIPE_ID) == [] and store.findings_for_document(ORIG)
    assert any(getattr(x, "reason", None) == "off_topic" for x in caplog.records)


def test_worker_passes_neardup_groups_and_suppresses_the_repeat_alert(r, store, registry, catalogue):
    pub = GroupRecorder(thresholds={"M1": 0.0, "M2": 0.5, "M3": 0.0})
    idx = NearDupIndex(r, NearDupSettings())
    w = make_worker(r, store, registry, catalogue, pub, gate=GATE, neardup=idx)
    handle(w, r, ORIG, COPY)
    assert pub.calls == [{ORIG: ORIG}, {COPY: ORIG}]
    kinds = [(e["type"], e["data"]["url"]) for e in pub.sent]
    assert ("finding.high_risk", "https://www.instagram.com/p/A/") in kinds
    assert ("finding.high_risk", "https://www.instagram.com/p/B/") not in kinds
    assert ("finding.created", "https://www.instagram.com/p/B/") in kinds
    copy_findings = store.findings_for_document(COPY)
    assert copy_findings and all("https://www.instagram.com/p/A/" in f.summary for f in copy_findings)


def test_worker_without_index_calls_publish_as_before(r, store, registry, catalogue):
    class OneArg(NoopPublisher):
        def publish_findings(self, saved):  # the pre-change signature
            return super().publish_findings(saved)

    pub = OneArg()
    handle(make_worker(r, store, registry, catalogue, pub, gate=GATE), r, ORIG)
    assert pub.sent


def test_worker_records_the_embedder(r, store, registry, catalogue):
    handle(make_worker(r, store, registry, catalogue, NoopPublisher(), embedder=FakeEmbedder()), r, ORIG)
    assert all(f.model.embedder == "bge-m3" for f in store.findings_for_document(ORIG))


# ---- startup config ---------------------------------------------------------------------------


def llm(env=None):
    return LlmSettings.from_env(env or {})


def test_preprocessing_defaults():
    p = preprocessing_from_env({}, claim_min_idle_ms=60000, llm_settings=llm())
    assert not p.embed.enabled and p.gate.settings.enabled and p.neardup.ttl_s == 2592000


@pytest.mark.parametrize("env,var", [({"EMBED_BASE_URL": "http://ollama:11434/v1", "EMBED_MODEL": ""}, "EMBED_MODEL"),
                                     ({"GATE_ENABLED": "maybe"}, "GATE_ENABLED"),
                                     ({"NEARDUP_BANDS": "30"}, "NEARDUP_BANDS")])
def test_preprocessing_config_errors_name_the_variable(env, var):
    with pytest.raises(ConfigError, match=var):
        preprocessing_from_env(env, claim_min_idle_ms=60000, llm_settings=llm())


def test_embed_timeout_counts_with_the_llm_budget_and_connect_margin():
    env = {"EMBED_BASE_URL": "http://ollama:11434/v1", "EMBED_TIMEOUT_S": "5"}
    llm_on = llm({"LLM_BASE_URL": "http://ollama:11434/v1", "LLM_MODEL": "gemma3:4b", "LLM_DOC_BUDGET_S": "51"})
    preprocessing_from_env(env, claim_min_idle_ms=60000, llm_settings=llm_on)          # 51 + 3 + 5 = 59 s
    llm_on = llm({"LLM_BASE_URL": "http://ollama:11434/v1", "LLM_MODEL": "gemma3:4b", "LLM_DOC_BUDGET_S": "52"})
    with pytest.raises(ConfigError, match="EMBED_TIMEOUT_S"):
        preprocessing_from_env(env, claim_min_idle_ms=60000, llm_settings=llm_on)      # 60 s


def test_disabled_llm_does_not_count():
    env = {"EMBED_BASE_URL": "http://ollama:11434/v1", "EMBED_TIMEOUT_S": "50"}
    preprocessing_from_env(env, claim_min_idle_ms=60000, llm_settings=llm({"LLM_DOC_BUDGET_S": "40"}))


def test_gate_terms_file_error_is_a_config_error(monkeypatch, tmp_path):
    import investwatch_analytics.worker as worker_mod

    bad = tmp_path / "gate_terms.yaml"
    bad.write_text("version: 1\nterms: []\n", encoding="utf-8")
    monkeypatch.setattr(worker_mod, "GATE_TERMS_PATH", bad)
    with pytest.raises(ConfigError, match="gate_terms.yaml"):
        preprocessing_from_env({}, claim_min_idle_ms=60000, llm_settings=llm())


def test_main_exits_2_on_bad_embeddings_config(capsys):
    from investwatch_analytics.worker import main

    env = {"DATABASE_URL": "postgresql://u@127.0.0.1:1/db", "REDIS_URL": "redis://127.0.0.1:1/0",
           "EMBED_BASE_URL": "http://ollama:11434/v1", "EMBED_MODEL": ""}
    assert main(env) == 2
    out = capsys.readouterr().out
    assert "EMBED_MODEL" in out and "config_error" in out


# ---- CLI --------------------------------------------------------------------------------------


def write_docs(tmp_path):
    p = tmp_path / "docs.json"
    p.write_text(json.dumps([make_doc(id=ORIG, url="https://www.instagram.com/p/A/", text=POST, **SOCIAL),
                             make_doc(id=RECIPE_ID, url="https://www.instagram.com/p/C/",
                                      text="Przepis na sernik babci.", **SOCIAL)], ensure_ascii=False),
                 encoding="utf-8")
    return p


def cli(tmp_path, monkeypatch, capsys, env, *args):
    from investwatch_analytics import cli as cli_mod

    for k, v in env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("REGISTRY_CSV", str(SEED_REGISTRY))
    code = cli_mod.main([str(write_docs(tmp_path)), "--no-llm", *args])
    return code, json.loads(capsys.readouterr().out)


def test_cli_uses_gate_and_embedder(stub_llm, tmp_path, monkeypatch, capsys):
    stub_llm.default = Reply(body=json.dumps({"data": [{"embedding": [1.0] * 8}]}).encode())
    code, findings = cli(tmp_path, monkeypatch, capsys, {"EMBED_BASE_URL": stub_llm.base_url, "EMBED_DIM": "8"})
    assert code == 0 and findings
    assert {f["document_id"] for f in findings} == {ORIG}             # the recipe is gated out
    assert all(f["model"]["embedder"] == "bge-m3" for f in findings)
    assert stub_llm.requests and all(r["path"] == "/v1/embeddings" for r in stub_llm.requests)


def test_cli_no_embed_forces_embeddings_off(stub_llm, tmp_path, monkeypatch, capsys):
    code, findings = cli(tmp_path, monkeypatch, capsys, {"EMBED_BASE_URL": stub_llm.base_url, "EMBED_DIM": "8"},
                         "--no-embed")
    assert code == 0 and findings and all(f["model"]["embedder"] is None for f in findings)
    assert stub_llm.requests == []


def test_cli_bad_embeddings_config_exits_2(tmp_path, monkeypatch, capsys):
    from investwatch_analytics import cli as cli_mod

    monkeypatch.setenv("EMBED_BASE_URL", "http://ollama:11434/v1")
    monkeypatch.setenv("EMBED_MODEL", "")
    assert cli_mod.main([str(write_docs(tmp_path))]) == 2


def test_cli_passes_the_gate_to_analyze(tmp_path, monkeypatch, capsys):
    from investwatch_analytics import cli as cli_mod

    seen = []
    monkeypatch.setattr(cli_mod, "analyze", lambda d, **kw: seen.append(kw) or [])
    monkeypatch.setenv("REGISTRY_CSV", str(SEED_REGISTRY))
    assert cli_mod.main([str(write_docs(tmp_path)), "--no-llm"]) == 0
    capsys.readouterr()
    assert seen and all(isinstance(kw["gate"], Gate) and kw["gate"].settings.enabled for kw in seen)


def test_compose_empty_values_mean_defaults():
    """analytics/compose.yaml passes every key as `${X:-}` (an empty string when unset): empty must mean default."""
    import re
    from pathlib import Path

    compose = (Path(__file__).resolve().parents[1] / "compose.yaml").read_text(encoding="utf-8")
    keys = re.findall(r"^\s+((?:EMBED|GATE|NEARDUP)_[A-Z_]+): \$\{\1:-([^}]*)\}", compose, re.M)
    assert len(keys) == 16
    env = {k: default for k, default in keys}
    env["EMBED_BASE_URL"] = "http://ollama:11434/v1"
    p = preprocessing_from_env(env, claim_min_idle_ms=60000, llm_settings=llm())
    assert p.embed.model == "bge-m3" and p.embed.dim == 1024 and p.gate.settings.enabled
    assert p.neardup.num_perm == 128
