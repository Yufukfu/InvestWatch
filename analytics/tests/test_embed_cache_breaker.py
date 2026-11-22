"""Embedding cache, circuit breaker and the never-raising embedder (analytics-embeddings task group 3)."""

from __future__ import annotations

import base64
import json
import logging

import fakeredis
import numpy as np
import pytest
import redis

from llm_stub import Reply, closed_port_url
from investwatch_analytics.config import EmbedSettings
from investwatch_analytics.embeddings import build_embedder
from investwatch_analytics.embeddings.breaker import Breaker
from investwatch_analytics.embeddings.cache import EmbedCache, cache_key, variant
from investwatch_analytics.embeddings.embedder import EmbedOutcome, HttpEmbedder

HASH = "a" * 64


def body(values) -> bytes:
    return json.dumps({"data": [{"embedding": list(values)}]}).encode()


def vec(dim=8, first=1.0):
    return [first] + [1.0] * (dim - 1)


def settings(base_url, **env) -> EmbedSettings:
    return EmbedSettings.from_env({"EMBED_BASE_URL": base_url, "EMBED_DIM": "8", **env})


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class BrokenRedis:
    """Raises a connection error on every call (a Redis outage)."""

    def __init__(self):
        self.calls = 0

    def __getattr__(self, name):
        def fail(*a, **k):
            self.calls += 1
            raise redis.ConnectionError("down")
        return fail


@pytest.fixture
def r():
    return fakeredis.FakeRedis(decode_responses=True)


# ---- cache key --------------------------------------------------------------------------------


def test_key_shape_and_variant():
    s = settings("http://127.0.0.1:1/v1")
    key = cache_key(s, HASH)
    assert key.startswith("iw:emb:v1:") and key.endswith(":" + HASH)
    assert len(variant(s)) == 12


@pytest.mark.parametrize("env", [{"EMBED_MODEL": "multilingual-e5-large"}, {"EMBED_DIM": "16"},
                                 {"EMBED_MAX_CHARS": "2000"}])
def test_variant_changes_with_model_dim_and_input_length(env):
    base = settings("http://127.0.0.1:1/v1")
    other = EmbedSettings.from_env({"EMBED_BASE_URL": "http://127.0.0.1:1/v1", "EMBED_DIM": "8", **env})
    assert variant(base) != variant(other)


def test_variant_ignores_url_and_key():
    a = settings("http://127.0.0.1:1/v1")
    b = settings("http://ollama:11434/v1", EMBED_API_KEY="k")
    assert variant(a) == variant(b)


# ---- cache ------------------------------------------------------------------------------------


def test_cache_round_trip_through_decode_responses_client(r):
    s = settings("http://127.0.0.1:1/v1")
    c = EmbedCache(r, s)
    v = np.arange(1, 9, dtype=np.float32)
    v /= np.linalg.norm(v)
    c.put(HASH, v)
    raw = r.get(cache_key(s, HASH))
    assert isinstance(raw, str)
    got = c.get(HASH)
    assert got.dtype == np.float32 and np.array_equal(got, v)
    assert 0 < r.ttl(cache_key(s, HASH)) <= 604800


def test_cache_ttl_from_settings(r):
    s = settings("http://127.0.0.1:1/v1", EMBED_CACHE_TTL_S="60")
    EmbedCache(r, s).put(HASH, np.ones(8, dtype=np.float32) / np.sqrt(8))
    assert 0 < r.ttl(cache_key(s, HASH)) <= 60


def test_cache_wrong_length_is_a_miss(r):
    s = settings("http://127.0.0.1:1/v1")
    r.set(cache_key(s, HASH), base64.b64encode(np.ones(4, dtype=np.float32).tobytes()).decode())
    assert EmbedCache(r, s).get(HASH) is None


@pytest.mark.parametrize("raw", ["%%%not-base64%%%", base64.b64encode(b"\x00" * 31).decode(),
                                 base64.b64encode(np.full(8, np.nan, dtype=np.float32).tobytes()).decode(),
                                 base64.b64encode(np.zeros(8, dtype=np.float32).tobytes()).decode()],
                         ids=["garbage", "odd-bytes", "nan", "zeros"])
def test_cache_corrupt_value_is_a_miss(r, raw):
    s = settings("http://127.0.0.1:1/v1")
    r.set(cache_key(s, HASH), raw)
    assert EmbedCache(r, s).get(HASH) is None


def test_cache_redis_down_is_a_miss_and_skipped_write(caplog):
    s = settings("http://127.0.0.1:1/v1")
    c = EmbedCache(BrokenRedis(), s)
    with caplog.at_level(logging.WARNING):
        assert c.get(HASH) is None
        c.put(HASH, np.ones(8, dtype=np.float32))
    assert [getattr(x, "reason", None) for x in caplog.records].count("embed_cache_unavailable") == 2


# ---- breaker ----------------------------------------------------------------------------------


def test_breaker_opens_after_n_failures_and_half_opens():
    clock = Clock()
    b = Breaker(3, 60, clock)
    for _ in range(2):
        assert b.allow()
        b.failure()
    assert b.allow()
    b.failure()
    assert not b.allow()
    clock.t += 59.9
    assert not b.allow()
    clock.t += 0.2
    assert b.allow()        # half-open: one trial call
    assert not b.allow()    # only one
    b.success()
    assert b.allow() and b.allow()


def test_breaker_half_open_failure_reopens():
    clock = Clock()
    b = Breaker(1, 10, clock)
    b.failure()
    clock.t += 10
    assert b.allow()
    b.failure()
    assert not b.allow()
    clock.t += 9.9
    assert not b.allow()


def test_breaker_success_resets_the_streak():
    b = Breaker(3, 60, Clock())
    b.failure()
    b.failure()
    b.success()
    b.failure()
    b.failure()
    assert b.allow()


# ---- embedder ---------------------------------------------------------------------------------


def test_embedder_ok_then_cached(stub_llm, r):
    stub_llm.default = Reply(body=body(vec()))
    e = HttpEmbedder(settings(stub_llm.base_url), redis=r)
    first = e.embed("Zarabiaj 18% rocznie", HASH)
    second = e.embed("Zarabiaj 18% rocznie", HASH)
    assert isinstance(first, EmbedOutcome)
    assert first.status == "ok" and first.model == "bge-m3" and first.vector is not None
    assert second.status == "cached" and second.model == "bge-m3"
    assert np.array_equal(first.vector, second.vector)
    assert len(stub_llm.requests) == 1


def test_model_swap_misses_the_cache(stub_llm, r):
    stub_llm.default = Reply(body=body(vec()))
    HttpEmbedder(settings(stub_llm.base_url), redis=r).embed("x", HASH)
    out = HttpEmbedder(settings(stub_llm.base_url, EMBED_MODEL="multilingual-e5-large"), redis=r).embed("x", HASH)
    assert out.status == "ok" and out.model == "multilingual-e5-large"
    assert len(stub_llm.requests) == 2


def test_corrupt_entry_is_overwritten(stub_llm, r):
    s = settings(stub_llm.base_url)
    r.set(cache_key(s, HASH), base64.b64encode(np.ones(4, dtype=np.float32).tobytes()).decode())
    stub_llm.default = Reply(body=body(vec()))
    out = HttpEmbedder(s, redis=r).embed("x", HASH)
    assert out.status == "ok" and len(stub_llm.requests) == 1
    assert EmbedCache(r, s).get(HASH) is not None


def test_rejected_vector_is_not_cached(stub_llm, r):
    s = settings(stub_llm.base_url)
    stub_llm.script = [Reply(body=body(vec(6))), Reply(body=body(vec()))]
    e = HttpEmbedder(s, redis=r)
    bad = e.embed("x", HASH)
    assert bad.vector is None and bad.model is None and bad.status == "embed_malformed"
    assert r.get(cache_key(s, HASH)) is None
    assert e.embed("x", HASH).status == "ok"


def test_cache_down_still_embeds(stub_llm):
    stub_llm.default = Reply(body=body(vec()))
    broken = BrokenRedis()
    out = HttpEmbedder(settings(stub_llm.base_url), redis=broken).embed("x", HASH)
    assert out.status == "ok" and out.vector is not None and broken.calls == 2


def test_no_stored_hash_embeds_without_the_cache(stub_llm, r):
    stub_llm.default = Reply(body=body(vec()))
    e = HttpEmbedder(settings(stub_llm.base_url), redis=r)
    assert e.embed("x", None).status == "ok" and e.embed("x", None).status == "ok"
    assert len(stub_llm.requests) == 2 and r.keys("iw:emb:*") == []


def test_empty_stored_hash_is_treated_as_none(stub_llm, r):
    stub_llm.default = Reply(body=body(vec()))
    HttpEmbedder(settings(stub_llm.base_url), redis=r).embed("x", "")
    assert r.keys("iw:emb:*") == []


def test_no_redis_no_cache(stub_llm):
    stub_llm.default = Reply(body=body(vec()))
    e = HttpEmbedder(settings(stub_llm.base_url))
    assert e.embed("x", HASH).status == "ok" and e.embed("x", HASH).status == "ok"
    assert len(stub_llm.requests) == 2


@pytest.mark.parametrize("reply,status", [
    (Reply(status=404, body=b"{}"), "embed_unavailable"),
    (Reply(status=500, body=b"{}"), "embed_unavailable"),
    (Reply(body=b"not json"), "embed_malformed"),
    (Reply(body=body(vec(8, 0.0)[:1] + [0.0] * 7)), "embed_malformed"),
])
def test_failures_never_raise(stub_llm, reply, status, caplog):
    stub_llm.default = reply
    with caplog.at_level(logging.WARNING):
        out = HttpEmbedder(settings(stub_llm.base_url)).embed("Przepis na sernik", HASH)
    assert out == EmbedOutcome(vector=None, model=None, status=status)
    assert "Przepis" not in "\n".join(f"{x.getMessage()} {x.__dict__}" for x in caplog.records)


def test_timeout_status(stub_llm):
    stub_llm.default = Reply(body=body(vec()), sleep_s=2)
    out = HttpEmbedder(settings(stub_llm.base_url, EMBED_TIMEOUT_S="0.5")).embed("x", HASH)
    assert out.status == "embed_timeout" and out.vector is None


def test_empty_text_is_not_sent(stub_llm):
    out = HttpEmbedder(settings(stub_llm.base_url)).embed("   ", HASH)
    assert out.status == "empty_text" and out.vector is None and stub_llm.requests == []


def test_breaker_opens_on_connection_refused_and_skips_calls():
    clock = Clock()
    e = HttpEmbedder(settings(closed_port_url()), clock=clock)
    for _ in range(3):
        assert e.embed("x", HASH).status == "embed_unavailable"
    out = e.embed("x", HASH)
    assert out.status == "breaker_open" and out.vector is None


def test_breaker_open_still_serves_the_cache(stub_llm, r):
    s = settings(stub_llm.base_url)
    stub_llm.script = [Reply(body=body(vec()))] + [Reply(status=500, body=b"{}")] * 3
    clock = Clock()
    e = HttpEmbedder(s, redis=r, clock=clock)
    e.embed("x", HASH)
    for i in range(3):
        e.embed("y", f"{i:064d}")
    assert e.embed("z", "f" * 64).status == "breaker_open"
    assert e.embed("x", HASH).status == "cached"


def test_breaker_half_open_success(stub_llm):
    stub_llm.script = [Reply(status=500, body=b"{}")] * 3 + [Reply(body=body(vec()))]
    clock = Clock()
    e = HttpEmbedder(settings(stub_llm.base_url), clock=clock)
    for _ in range(3):
        e.embed("x", HASH)
    clock.t += 61
    assert e.embed("x", HASH).status == "ok"
    stub_llm.default = Reply(body=body(vec()))
    assert e.embed("x", HASH).status == "ok"


def test_malformed_does_not_count_toward_the_breaker(stub_llm):
    stub_llm.default = Reply(body=b"not json")
    e = HttpEmbedder(settings(stub_llm.base_url), clock=Clock())
    for _ in range(5):
        assert e.embed("x", HASH).status == "embed_malformed"
    assert len(stub_llm.requests) == 5


# ---- build ------------------------------------------------------------------------------------


def test_build_embedder_disabled_returns_none():
    assert build_embedder(EmbedSettings.from_env({})) is None


def test_build_embedder_enabled(stub_llm, r):
    e = build_embedder(settings(stub_llm.base_url), redis=r)
    assert isinstance(e, HttpEmbedder) and e.model == "bge-m3"


# ---- review fixes (group 3) -------------------------------------------------------------------


def test_non_utf8_cached_value_is_a_miss_and_overwritten(stub_llm):
    server = fakeredis.FakeServer()
    raw = fakeredis.FakeRedis(server=server)
    dec = fakeredis.FakeRedis(server=server, decode_responses=True)
    s = settings(stub_llm.base_url)
    raw.set(cache_key(s, HASH), b"\xff\xfe")
    stub_llm.default = Reply(body=body(vec()))
    out = HttpEmbedder(s, redis=dec).embed("x", HASH)
    assert out.status == "ok" and len(stub_llm.requests) == 1
    assert EmbedCache(dec, s).get(HASH) is not None


def test_oversized_cached_value_is_rejected_before_decoding(r, monkeypatch):
    import investwatch_analytics.embeddings.cache as cache_mod

    s = settings("http://127.0.0.1:1/v1")
    r.set(cache_key(s, HASH), base64.b64encode(np.ones(100_000, dtype=np.float32).tobytes()).decode())

    def boom(*a, **k):
        raise AssertionError("an oversized value must not be turned into floats")

    monkeypatch.setattr(cache_mod, "validate_vector", boom)
    assert EmbedCache(r, s).get(HASH) is None


class RaisingClient:
    model = "bge-m3"

    def __init__(self):
        self.calls = 0

    def embed(self, text):
        self.calls += 1
        raise RuntimeError("unexpected")


def test_unexpected_client_error_never_raises_and_counts(caplog):
    clock = Clock()
    c = RaisingClient()
    e = HttpEmbedder(settings("http://127.0.0.1:1/v1"), clock=clock, client=c)
    with caplog.at_level(logging.WARNING):
        for _ in range(3):
            assert e.embed("x", HASH) == EmbedOutcome(None, None, "embed_unavailable")
    assert e.embed("x", HASH).status == "breaker_open" and c.calls == 3
    assert any(getattr(x, "error", None) == "RuntimeError" for x in caplog.records)


def test_unexpected_error_in_half_open_trial_reopens():
    clock = Clock()
    c = RaisingClient()
    e = HttpEmbedder(settings("http://127.0.0.1:1/v1"), clock=clock, client=c)
    for _ in range(3):
        e.embed("x", HASH)
    clock.t += 61
    assert e.embed("x", HASH).status == "embed_unavailable"   # the trial call
    clock.t += 61
    assert e.embed("x", HASH).status == "embed_unavailable"   # not stuck: a new trial after the cooldown
    assert c.calls == 5


def test_breaker_failed_trial_reopens_with_default_threshold():
    clock = Clock()
    b = Breaker(3, 60, clock)
    for _ in range(3):
        b.failure()
    clock.t += 60
    assert b.allow()
    b.failure()
    assert not b.allow()
    clock.t += 59.9
    assert not b.allow()
