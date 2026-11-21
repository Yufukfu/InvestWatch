"""Response cache, per-document budget and circuit breaker (analytics-llm-p0 task group 10). Stub server only."""

from __future__ import annotations

import logging
from pathlib import Path

import fakeredis
import pytest
import redis

from llm_stub import Reply, closed_port_url
from investwatch_analytics.config import LlmSettings
from investwatch_analytics.llm.judge import SemanticCheck
from investwatch_analytics.preprocessing import preprocess

KNF = "Działamy pod nadzorem KNF – Twoje środki są bezpieczne."
TEXT = f"Konto Premium Alfa Inwestycje. {KNF} Otwórz konto w 5 minut."
R17 = SemanticCheck("R17", "Czy odwołanie do KNF sugeruje aprobatę produktu?", ("fail", "pass", "uncertain"))
FAIL = {"rule_id": "R17", "result": "fail", "evidence_quote": KNF, "explanation": "Sugeruje aprobatę."}


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def make(url, *, cache=None, clock=None, **env):
    from investwatch_analytics.llm.judge import HttpJudge

    settings = LlmSettings.from_env({"LLM_BASE_URL": url, "LLM_MODEL": "gemma3:4b", **env})
    return HttpJudge(settings, redis=cache, clock=clock or Clock())


def ask(judge, text=TEXT, checks=(R17,), module="M2", context=""):
    pre = preprocess(text)
    return judge.judge(module=module, module_context=context, text=text, content_hash=pre.content_hash,
                       sentences=pre.sentences, checks=list(checks))


# ---- cache ------------------------------------------------------------------------------------------


def test_rescan_is_served_from_the_cache(stub_llm):
    r = fakeredis.FakeRedis(decode_responses=True)
    stub_llm.default = Reply.results(FAIL)
    first = ask(make(stub_llm.base_url, cache=r))
    second = ask(make(stub_llm.base_url, cache=r))  # a fresh judge, as after a worker restart
    assert len(stub_llm.requests) == 1 and first.verdicts == second.verdicts
    [key] = r.keys("iw:llm:*")
    assert key.startswith("iw:llm:v1:M2:") and 0 < r.ttl(key) <= 604800


def test_model_swap_misses(stub_llm):
    r = fakeredis.FakeRedis(decode_responses=True)
    ask(make(stub_llm.base_url, cache=r))
    ask(make(stub_llm.base_url, cache=r, LLM_MODEL="other-model"))
    assert len(stub_llm.requests) == 2


def test_question_edit_misses(stub_llm):
    r = fakeredis.FakeRedis(decode_responses=True)
    ask(make(stub_llm.base_url, cache=r))
    edited = SemanticCheck("R17", "Czy treść sugeruje aprobatę KNF?", R17.allowed)
    ask(make(stub_llm.base_url, cache=r), checks=(edited,))
    assert len(stub_llm.requests) == 2


def test_other_module_or_checks_miss(stub_llm):
    r = fakeredis.FakeRedis(decode_responses=True)
    ask(make(stub_llm.base_url, cache=r))
    ask(make(stub_llm.base_url, cache=r), module="M1")
    ask(make(stub_llm.base_url, cache=r),
        checks=(R17, SemanticCheck("R18", "Q?", ("fail", "pass", "uncertain"))))
    assert len(stub_llm.requests) == 3
    assert any(k.startswith("iw:llm:v1:M1:") for k in r.keys("iw:llm:*"))  # namespaced per module


def test_chunk_size_change_misses(stub_llm):
    r = fakeredis.FakeRedis(decode_responses=True)
    text = " ".join(f"Neutralne zdanie numer {i:03d} o ofercie banku." for i in range(40)) + " " + KNF
    ask(make(stub_llm.base_url, cache=r, LLM_CHUNK_CHARS="900"), text=text)
    n = len(stub_llm.requests)
    ask(make(stub_llm.base_url, cache=r, LLM_CHUNK_CHARS="1000"), text=text)
    assert len(stub_llm.requests) > n


def test_malformed_answer_is_not_cached(stub_llm):
    r = fakeredis.FakeRedis(decode_responses=True)
    stub_llm.script.append(Reply(content='{"results": [{"rule_id": "R17"'))
    stub_llm.script.append(Reply.results(FAIL))
    assert ask(make(stub_llm.base_url, cache=r)).verdicts == {}
    assert ask(make(stub_llm.base_url, cache=r)).verdicts["R17"].result == "fail"
    assert len(stub_llm.requests) == 2


def test_failed_call_is_not_cached(stub_llm):
    r = fakeredis.FakeRedis(decode_responses=True)
    stub_llm.script.append(Reply(status=500))
    ask(make(stub_llm.base_url, cache=r))
    assert r.keys("iw:llm:*") == []


def test_cache_hit_reruns_quote_verification(stub_llm):
    """A cached answer is re-verified against the chunk: tampering in Redis cannot inject evidence."""
    import json

    r = fakeredis.FakeRedis(decode_responses=True)
    stub_llm.default = Reply.results(FAIL)
    ask(make(stub_llm.base_url, cache=r))
    [key] = r.keys("iw:llm:*")
    r.set(key, json.dumps({"results": [{**FAIL, "evidence_quote": "Produkt zatwierdzony przez KNF"}]}))
    v = ask(make(stub_llm.base_url, cache=r)).verdicts["R17"]
    assert v.result == "uncertain" and v.evidence is None and len(stub_llm.requests) == 1


def test_corrupt_cache_entry_is_a_miss(stub_llm):
    r = fakeredis.FakeRedis(decode_responses=True)
    stub_llm.default = Reply.results(FAIL)
    ask(make(stub_llm.base_url, cache=r))
    [key] = r.keys("iw:llm:*")
    r.set(key, "{not json")
    assert ask(make(stub_llm.base_url, cache=r)).verdicts["R17"].result == "fail"
    assert len(stub_llm.requests) == 2


class BrokenRedis:
    def get(self, *a, **k):
        raise redis.ConnectionError("down")

    def set(self, *a, **k):
        raise redis.ConnectionError("down")


def test_redis_down_is_a_miss_and_never_raises(stub_llm, caplog):
    caplog.set_level(logging.INFO)
    stub_llm.default = Reply.results(FAIL)
    out = ask(make(stub_llm.base_url, cache=BrokenRedis()))
    assert out.verdicts["R17"].result == "fail" and len(stub_llm.requests) == 1
    assert any(getattr(rec, "reason", None) == "llm_cache_unavailable" for rec in caplog.records)


def test_no_cache_without_redis(stub_llm):
    ask(make(stub_llm.base_url))
    ask(make(stub_llm.base_url))
    assert len(stub_llm.requests) == 2


# ---- budget ------------------------------------------------------------------------------------------


def test_budget_exhausted_skips_the_remaining_calls(stub_llm, caplog):
    caplog.set_level(logging.INFO)
    clock = Clock()
    judge = make(stub_llm.base_url, clock=clock, LLM_DOC_BUDGET_S="10")
    judge.begin_document()
    ask(judge)
    clock.t += 11
    out = ask(judge, module="M1")
    assert out.status == "budget_exhausted" and out.verdicts == {} and len(stub_llm.requests) == 1
    assert any(getattr(rec, "reason", None) == "llm_budget_exhausted" for rec in caplog.records)


def test_budget_resets_per_document(stub_llm):
    clock = Clock()
    judge = make(stub_llm.base_url, clock=clock, LLM_DOC_BUDGET_S="10")
    judge.begin_document()
    clock.t += 11
    judge.begin_document()
    assert ask(judge).status == "ok"


def test_remaining_budget_caps_the_request_timeout(stub_llm):
    import time

    stub_llm.script.append(Reply(sleep_s=3))
    judge = make(stub_llm.base_url, LLM_TIMEOUT_S="20", LLM_DOC_BUDGET_S="0.5", clock=time.monotonic)
    judge.begin_document()
    start = time.perf_counter()
    out = ask(judge)
    assert out.status == "unavailable" and time.perf_counter() - start < 2.0


def test_pipeline_starts_a_budget_per_document(stub_llm, monkeypatch):
    from conftest import make_doc
    from investwatch_analytics.models import ScrapedDocument
    from investwatch_analytics.pipeline import analyze
    from investwatch_analytics.registry import Registry
    from investwatch_analytics.rules.engine import Catalogue
    from investwatch_analytics.config import Settings

    judge = make(stub_llm.base_url)
    calls = []
    monkeypatch.setattr(judge, "begin_document", lambda: calls.append(1))
    doc = ScrapedDocument.model_validate(make_doc(text=TEXT))
    analyze(doc, registry=Registry.from_csv(Path(__file__).resolve().parents[1] / "registry" / "seed.csv"), catalogue=Catalogue.load(), judge=judge)
    assert calls == [1]


# ---- circuit breaker ------------------------------------------------------------------------------------


def test_breaker_opens_after_consecutive_failures():
    clock = Clock()
    judge = make(closed_port_url(), clock=clock, LLM_BREAKER_FAILURES="3", LLM_BREAKER_COOLDOWN_S="60")
    for _ in range(3):
        assert ask(judge).status == "unavailable"
    calls = []
    judge._client.complete = lambda *a, **k: calls.append(1) or {"results": []}
    clock.t += 10
    assert ask(judge).status == "unavailable" and calls == []  # open: no call during the cooldown


def test_breaker_half_open_success_closes(stub_llm):
    clock = Clock()
    judge = make(stub_llm.base_url, clock=clock, LLM_BREAKER_FAILURES="2", LLM_BREAKER_COOLDOWN_S="60")
    stub_llm.script.extend([Reply(status=500), Reply(status=500)])
    ask(judge), ask(judge)
    clock.t += 61
    stub_llm.default = Reply.results(FAIL)
    assert ask(judge).status == "ok"
    assert ask(judge).status == "ok" and len(stub_llm.requests) == 4


def test_breaker_half_open_failure_reopens(stub_llm):
    clock = Clock()
    judge = make(stub_llm.base_url, clock=clock, LLM_BREAKER_FAILURES="2", LLM_BREAKER_COOLDOWN_S="60")
    stub_llm.default = Reply(status=500)
    ask(judge), ask(judge)
    clock.t += 61
    ask(judge)                       # the one half-open try fails
    n = len(stub_llm.requests)
    clock.t += 5
    ask(judge)
    assert len(stub_llm.requests) == n  # open again


def test_malformed_does_not_count_toward_the_breaker(stub_llm):
    clock = Clock()
    judge = make(stub_llm.base_url, clock=clock, LLM_BREAKER_FAILURES="2")
    stub_llm.default = Reply(content="[1]")
    for _ in range(4):
        ask(judge)
    assert len(stub_llm.requests) == 4


def test_a_success_resets_the_failure_count(stub_llm):
    clock = Clock()
    judge = make(stub_llm.base_url, clock=clock, LLM_BREAKER_FAILURES="2")
    stub_llm.script.extend([Reply(status=500), Reply.results(FAIL), Reply(status=500)])
    ask(judge), ask(judge), ask(judge)
    stub_llm.default = Reply.results(FAIL)
    assert ask(judge).status == "ok"  # failures were not consecutive: still closed


def test_build_judge_passes_the_redis_client():
    from investwatch_analytics.llm import build_judge

    r = fakeredis.FakeRedis(decode_responses=True)
    j = build_judge(LlmSettings.from_env({"LLM_BASE_URL": "http://ollama:11434/v1", "LLM_MODEL": "m"}), redis=r)
    assert j._cache is not None
