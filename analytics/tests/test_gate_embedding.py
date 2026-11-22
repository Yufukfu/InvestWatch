"""Embedding rescue in the topic gate (analytics-embedding-gate group 1). FakeEmbedder only, never a model."""

from __future__ import annotations

import logging

import numpy as np
import pytest
import yaml

from investwatch_analytics.config import ConfigError, GateSettings
from investwatch_analytics.embeddings import EmbedOutcome
from investwatch_analytics.gate import GateTermsError, evaluate, load_terms
from investwatch_analytics.gate_embedding import OFF_TOPIC, GateEmbedding, decide, seed_hash
from investwatch_analytics.preprocessing import normalize

E_OFFER, E_SIGNAL, E_OFF = np.eye(3, dtype=np.float32)
SEEDS = {"offer": ["oferta a", "oferta b"], "signals": ["sygnal a"], OFF_TOPIC: ["mecz", "przepis"]}
SEED_VECS = {"oferta a": E_OFFER, "oferta b": E_OFFER, "sygnal a": E_SIGNAL, "mecz": E_OFF, "przepis": E_OFF}


def unit(*xs) -> np.ndarray:
    v = np.asarray(xs, dtype=np.float32)
    return v / np.linalg.norm(v)


class FakeEmbedder:
    """Hand-made vectors: seeds by text, documents from `docs`; a status instead of a vector on demand."""

    model = "bge-m3"

    def __init__(self, docs=None, fail=None):
        self.docs = docs or {}
        self.fail = fail or {}  # text -> status
        self.calls: list[tuple[str, str | None]] = []

    def embed(self, text, content_hash):
        self.calls.append((text, content_hash))
        if text in self.fail:
            return EmbedOutcome(None, None, self.fail[text])
        vec = SEED_VECS.get(text, self.docs.get(text))
        return EmbedOutcome(None, None, "embed_unavailable") if vec is None else EmbedOutcome(vec, "bge-m3", "ok")


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def build(embedder=None, margin=0.05, clock=None, seeds=SEEDS, retry_s=60):
    return GateEmbedding(embedder or FakeEmbedder(), seeds, GateSettings(embed_min_margin=margin),
                         retry_s=retry_s, clock=clock or Clock())


# ---- settings ---------------------------------------------------------------------------------


def test_embed_settings_defaults():
    g = GateSettings.from_env({})
    assert g.embed_min_margin == 0.03 and g.embed_min_chars == 40


@pytest.mark.parametrize("raw", ["-0.01", "1.01", "abc", "nan", "inf"])
def test_margin_range(raw):
    with pytest.raises(ConfigError, match="GATE_EMBED_MIN_MARGIN"):
        GateSettings.from_env({"GATE_EMBED_MIN_MARGIN": raw})


@pytest.mark.parametrize("raw,expected", [("0", 0.0), ("1", 1.0), ("0.1", 0.1), ("", 0.03)])
def test_margin_bounds_inclusive(raw, expected):
    assert GateSettings.from_env({"GATE_EMBED_MIN_MARGIN": raw}).embed_min_margin == expected


@pytest.mark.parametrize("raw", ["0", "-5", "abc", "1.5"])
def test_min_chars_positive_int(raw):
    with pytest.raises(ConfigError, match="GATE_EMBED_MIN_CHARS"):
        GateSettings.from_env({"GATE_EMBED_MIN_CHARS": raw})


def test_min_chars_one_accepted():
    assert GateSettings.from_env({"GATE_EMBED_MIN_CHARS": "1"}).embed_min_chars == 1


# ---- seed classes -----------------------------------------------------------------------------


def write(tmp_path, data):
    p = tmp_path / "gate_terms.yaml"
    p.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return p


BASE = {"version": 1, "terms": ["zysk*"]}


@pytest.mark.parametrize("centroids", [{"offer": ["a"]}, {OFF_TOPIC: ["a"]}, {"offer": ["a"], "signals": ["b"]}],
                         ids=["no-off-topic", "off-topic-only", "two-on-topic-no-off-topic"])
def test_seed_classes_need_off_topic_and_one_more(tmp_path, centroids):
    with pytest.raises(GateTermsError) as exc:
        load_terms(write(tmp_path, {**BASE, "centroids": centroids}))
    assert "centroids" in str(exc.value) and "gate_terms.yaml" in str(exc.value)


def test_seed_classes_valid_and_empty_allowed(tmp_path):
    assert load_terms(write(tmp_path, {**BASE, "centroids": {"offer": ["a"], OFF_TOPIC: ["b"]}})).centroids
    assert load_terms(write(tmp_path, BASE)).centroids == {}


def test_shipped_seeds_have_off_topic_and_avoid_the_dictionary():
    terms = load_terms()
    assert OFF_TOPIC in terms.centroids and len(terms.centroids) >= 2
    # Off-topic seeds must not pass on the dictionary either (they would teach the wrong class).
    assert not any(evaluate(normalize(s), source_kind="third_party", firm_matched=False, terms=terms,
                            settings=GateSettings()).passed for s in terms.centroids[OFF_TOPIC])


# ---- warm -------------------------------------------------------------------------------------


def test_warm_builds_normalized_class_means():
    ge = build()
    assert not ge.ready
    assert ge.warm() is True and ge.ready
    assert set(ge.centroids) == {"offer", "signals", OFF_TOPIC}
    for c in ge.centroids.values():
        assert abs(float(np.linalg.norm(c)) - 1.0) < 1e-6
    np.testing.assert_allclose(ge.centroids["offer"], E_OFFER, atol=1e-6)


def test_warm_mean_of_two_different_seeds_is_normalized():
    seeds = {"offer": ["oferta a", "sygnal a"], OFF_TOPIC: ["mecz"]}
    ge = build(seeds=seeds)
    ge.warm()
    np.testing.assert_allclose(ge.centroids["offer"], unit(1, 1, 0), atol=1e-6)


def test_warm_uses_seed_hash_as_cache_key():
    emb = FakeEmbedder()
    build(emb).warm()
    assert ("oferta a", seed_hash("oferta a")) in emb.calls
    assert seed_hash("oferta a") != seed_hash("oferta b") and len(seed_hash("x")) == 64


def test_warm_stops_on_first_failed_seed(caplog):
    emb = FakeEmbedder(fail={"oferta a": "embed_timeout"})
    ge = build(emb)
    with caplog.at_level(logging.WARNING):
        assert ge.warm() is False
    assert not ge.ready and len(emb.calls) == 1
    assert any(r.getMessage() == "embedding gate degraded" and r.reason == "embed_timeout" for r in caplog.records)


def test_warm_is_rate_limited_and_retries_after_cooldown():
    clock = Clock()
    emb = FakeEmbedder(fail={"oferta a": "embed_unavailable"})
    ge = build(emb, clock=clock, retry_s=60)
    ge.warm()
    clock.t = 59.9
    assert ge.warm() is False and len(emb.calls) == 1  # too early: no call
    emb.fail = {}
    clock.t = 60.0
    assert ge.warm() is True and ge.ready


def test_warm_first_attempt_is_immediate_at_any_clock():
    clock = Clock()
    clock.t = 5.0
    ge = build(clock=clock)
    assert ge.warm() is True


def test_warm_does_nothing_once_built():
    emb = FakeEmbedder()
    ge = build(emb)
    ge.warm()
    n = len(emb.calls)
    assert ge.warm() is True and len(emb.calls) == n


def test_warm_restored_logged_after_failure(caplog):
    clock = Clock()
    emb = FakeEmbedder(fail={"oferta a": "embed_unavailable"})
    ge = build(emb, clock=clock)
    ge.warm()
    emb.fail = {}
    clock.t = 100
    with caplog.at_level(logging.INFO):
        ge.warm()
    assert any(r.getMessage() == "embedding gate restored" for r in caplog.records)


# ---- rescue -----------------------------------------------------------------------------------


DOC = "zupelnie inny tekst bez slow ze slownika, ale dlugi"


def ready(docs, margin=0.05):
    ge = build(FakeEmbedder(docs=docs), margin=margin)
    assert ge.warm()
    return ge


def test_rescue_passes_above_margin():
    r = ready({DOC: unit(0.8, 0, 0.6)}).rescue(DOC, "h1")
    assert r.path == "embedding" and r.passed
    assert r.similarity == pytest.approx(0.8, abs=1e-3) and r.margin == pytest.approx(0.2, abs=1e-3)
    assert r.outcome.model == "bge-m3"


def test_rescue_takes_the_best_on_topic_class_not_the_mean():
    # Close to `signals` only: the max over classes is 0.8; a pooled centroid would score lower.
    r = ready({DOC: unit(0, 0.8, 0.6)}).rescue(DOC, "h1")
    assert r.similarity == pytest.approx(0.8, abs=1e-3) and r.passed


def test_rescue_drops_below_margin():
    r = ready({DOC: unit(0.6, 0, 0.8)}).rescue(DOC, "h1")
    assert r.path == "embedding" and not r.passed and r.margin == pytest.approx(-0.2, abs=1e-3)


def test_rescue_margin_boundary_is_inclusive():
    v = unit(1, 0, 1)  # margin exactly 0
    assert ready({DOC: v}, margin=0.0).rescue(DOC, "h1").passed
    assert not ready({DOC: v}, margin=0.001).rescue(DOC, "h1").passed


def test_rescue_figures_rounded_to_three_places():
    r = ready({DOC: unit(0.81234, 0, 0.58321)}).rescue(DOC, "h1")
    assert r.similarity == round(r.similarity, 3) and r.margin == round(r.margin, 3)


def test_rescue_without_centroids_is_fallback_and_does_not_embed():
    emb = FakeEmbedder(docs={DOC: E_OFFER})
    ge = build(emb)
    r = ge.rescue(DOC, "h1")
    assert r.path == "dictionary_only_fallback" and not r.passed and r.outcome is None and emb.calls == []


def test_rescue_without_centroids_adds_no_log_line_to_the_warm_failure(caplog):
    clock = Clock()
    emb = FakeEmbedder(fail={"oferta a": "embed_unavailable"})
    ge = build(emb, clock=clock)
    with caplog.at_level(logging.INFO):
        ge.warm()
        ge.rescue(DOC, "h1")
        ge.rescue(DOC, "h2")
    assert [(r.getMessage(), r.reason) for r in caplog.records if r.getMessage().startswith("embedding gate")] == [
        ("embedding gate degraded", "embed_unavailable")]


def test_rescue_failed_vector_is_fallback_with_outcome():
    ge = ready({})
    ge._embedder.fail = {DOC: "breaker_open"}
    r = ge.rescue(DOC, "h1")
    assert r.path == "dictionary_only_fallback" and not r.passed and r.outcome.status == "breaker_open"
    assert r.similarity is None and r.margin is None


def test_degraded_logged_once_per_change_of_reason(caplog):
    ge = ready({})
    ge._embedder.fail = {DOC: "embed_unavailable", "b": "embed_unavailable", "c": "breaker_open"}
    caplog.clear()  # the `embedding gate ready` line of the build is captured when the root logger is at INFO
    with caplog.at_level(logging.INFO):
        ge.rescue(DOC, "h1")
        ge.rescue("b", "h2")
        ge.rescue("c", "h3")
    msgs = [(r.getMessage(), getattr(r, "reason", None)) for r in caplog.records
            if r.getMessage().startswith("embedding gate")]
    assert msgs == [("embedding gate degraded", "embed_unavailable"), ("embedding gate degraded", "breaker_open")]


def test_restored_after_degraded_rescue(caplog):
    ge = ready({DOC: E_OFFER})
    ge._embedder.fail = {"b": "embed_unavailable"}
    ge.rescue("b", "h2")
    caplog.clear()
    with caplog.at_level(logging.INFO):
        ge.rescue(DOC, "h1")
        ge.rescue(DOC, "h1")
    assert [r.getMessage() for r in caplog.records if r.getMessage().startswith("embedding gate")] == [
        "embedding gate restored"]


def test_rescue_never_raises_on_embedder_exception():
    class Boom(FakeEmbedder):
        def embed(self, text, content_hash):
            if text == DOC:
                raise RuntimeError("x")
            return super().embed(text, content_hash)

    ge = GateEmbedding(Boom(), SEEDS, GateSettings(), retry_s=60, clock=Clock())
    ge.warm()
    r = ge.rescue(DOC, "h1")
    assert r.path == "dictionary_only_fallback" and not r.passed


# ---- decide (dictionary first, then the rescue) -----------------------------------------------


TERMS = load_terms()
LONG_OFF = "Wczoraj wieczorem na stadionie miejskim odbyl sie mecz, kibice spiewali do konca"
LONG_ON = "Napisz do mnie prywatnie, pokaze Ci jak z odprawy zrobilam nowe auto w pol roku"


def dict_decision(text, source_kind="third_party", settings=None):
    return evaluate(normalize(text), source_kind=source_kind, firm_matched=False, terms=TERMS,
                    settings=settings or GateSettings())


def test_decide_dictionary_pass_never_calls_the_embedder():
    text = "Zainwestuj w CFD na forex, zyski 20% miesiecznie, kontakt w bio, nie przegap okazji"
    emb = FakeEmbedder(docs={text: E_OFF})
    ge = build(emb)
    ge.warm()
    n = len(emb.calls)
    d, out = decide(dict_decision(text), normalize(text), "h", ge, GateSettings())
    assert d.passed and d.reason == "dictionary" and d.path == "dictionary" and out is None and len(emb.calls) == n


def test_decide_no_embedder_is_fallback():
    d, out = decide(dict_decision(LONG_OFF), normalize(LONG_OFF), "h", None, GateSettings())
    assert not d.passed and d.reason == "off_topic" and d.path == "dictionary_only_fallback" and out is None


def test_decide_short_text_stays_dictionary_and_is_not_embedded():
    short = "pogoda na jutro"
    emb = FakeEmbedder(docs={short: E_OFFER})
    ge = build(emb)
    ge.warm()
    n = len(emb.calls)
    d, _ = decide(dict_decision(short), normalize(short), "h", ge, GateSettings(embed_min_chars=40))
    assert not d.passed and d.path == "dictionary" and len(emb.calls) == n


def test_decide_min_chars_boundary():
    text = "x" * 40
    ge = ready({text: E_OFFER})
    assert decide(dict_decision(text), text, "h", ge, GateSettings(embed_min_chars=40))[0].path == "embedding"
    assert decide(dict_decision(text), text, "h", ge, GateSettings(embed_min_chars=41))[0].path == "dictionary"


def test_decide_rescue_passes_with_reason_embedding():
    ge = ready({normalize(LONG_ON): unit(0.8, 0, 0.6)})
    d, out = decide(dict_decision(LONG_ON), normalize(LONG_ON), "h", ge, GateSettings())
    assert d.passed and d.reason == "embedding" and d.path == "embedding" and d.dict_hits == 0
    assert d.similarity == pytest.approx(0.8, abs=1e-3) and d.margin == pytest.approx(0.2, abs=1e-3)
    assert d.embedder == "bge-m3" and out.vector is not None


def test_decide_embedding_drop_keeps_off_topic():
    ge = ready({normalize(LONG_OFF): unit(0.1, 0, 0.9)})
    d, out = decide(dict_decision(LONG_OFF), normalize(LONG_OFF), "h", ge, GateSettings())
    assert not d.passed and d.reason == "off_topic" and d.path == "embedding" and d.margin < 0
    assert out is not None


def test_decide_degraded_rescue_is_fallback_and_hands_back_the_outcome():
    ge = ready({})
    ge._embedder.fail = {normalize(LONG_OFF): "embed_timeout"}
    d, out = decide(dict_decision(LONG_OFF), normalize(LONG_OFF), "h", ge, GateSettings())
    assert d.path == "dictionary_only_fallback" and not d.passed and out.status == "embed_timeout"


@pytest.mark.parametrize("source_kind,settings,reason", [
    ("firm_own", GateSettings(), "bypassed_firm_own"),
    ("third_party", GateSettings(enabled=False), "gate_disabled"),
])
def test_decide_bypass_and_disabled_untouched(source_kind, settings, reason):
    emb = FakeEmbedder(docs={normalize(LONG_OFF): E_OFFER})
    ge = build(emb)
    ge.warm()
    n = len(emb.calls)
    d, out = decide(dict_decision(LONG_OFF, source_kind, settings), normalize(LONG_OFF), "h", ge, settings)
    assert d.passed and d.reason == reason and d.path is None and out is None and len(emb.calls) == n


def test_log_extra_carries_path_and_margin():
    ge = ready({normalize(LONG_OFF): unit(0.1, 0, 0.9)})
    d, _ = decide(dict_decision(LONG_OFF), normalize(LONG_OFF), "h", ge, GateSettings())
    extra = d.log_extra()
    assert extra["gate_path"] == "embedding" and extra["margin"] is not None and extra["similarity"] is not None
    assert LONG_OFF not in str(extra)
