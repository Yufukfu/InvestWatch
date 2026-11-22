"""A bare JSON array answer is read as `{"results": <array>}` (change analytics-llm-bare-array).

Hosted `gemma-4-26b-a4b-it` answered 5 of 8 sampled gold-set calls with a bare array of result items. Stub server only.
"""

from __future__ import annotations

import json

import fakeredis
import pytest

from llm_stub import Reply
from investwatch_analytics.config import LlmSettings
from test_llm_cache_budget import ask as cached_ask
from test_llm_cache_budget import make
from test_llm_judge import ALFA, KNF, ask, item, judge_for


def client(stub):
    from investwatch_analytics.llm.client import ChatClient

    return ChatClient(LlmSettings.from_env({"LLM_BASE_URL": stub.base_url, "LLM_MODEL": "gemma3:4b"}))


def array(*items, wrap=lambda s: s) -> Reply:
    return Reply(content=wrap(json.dumps(list(items), ensure_ascii=False)))


@pytest.mark.parametrize("wrap", [
    lambda s: s,
    lambda s: f"<thought>Sprawdzam R17.</thought>\n{s}",
    lambda s: f"```json\n{s}\n```",
    lambda s: f"<thought>x</thought>```json\n{s}\n```",
], ids=["bare", "after-thought", "code-fence", "thought-and-fence"])
def test_client_reads_a_bare_array_as_results(stub_llm, wrap):
    stub_llm.script.append(array(item(), wrap=wrap))
    assert client(stub_llm).complete("s", "u") == {"results": [item()]}


def test_empty_array_is_a_valid_answer_without_verdicts(stub_llm):
    stub_llm.script.append(Reply(content="[]"))
    out = ask(judge_for(stub_llm.base_url))
    assert out.status == "ok" and out.verdicts == {}


def test_array_verdict_with_a_document_quote(stub_llm):
    stub_llm.script.append(array(item()))
    out = ask(judge_for(stub_llm.base_url))
    v = out.verdicts["R17"]
    assert out.status == "ok" and v.result == "fail" and v.evidence == KNF and v.evidence in ALFA


def test_array_verdict_quote_is_still_verified(stub_llm):
    stub_llm.script.append(array(item(quote="Produkt zatwierdzony przez KNF")))
    v = ask(judge_for(stub_llm.base_url)).verdicts["R17"]
    assert v.result == "uncertain" and v.evidence is None


def test_invalid_item_in_an_array_is_dropped(stub_llm):
    stub_llm.script.append(array(item(result="maybe"), item(rule_id="R99")))
    out = ask(judge_for(stub_llm.base_url))
    assert out.status == "ok" and out.verdicts == {}


def test_array_answer_is_cached_like_an_object(stub_llm):
    r = fakeredis.FakeRedis(decode_responses=True)
    stub_llm.default = array(item())
    first = cached_ask(make(stub_llm.base_url, cache=r))
    second = cached_ask(make(stub_llm.base_url, cache=r))
    assert len(stub_llm.requests) == 1 and first.verdicts == second.verdicts and first.verdicts["R17"].result == "fail"


@pytest.mark.parametrize("content, message", [
    ('"R17 fail"', "not a JSON object or array"), ("5", "not a JSON object or array"),
    ("true", "not a JSON object or array"), ("null", "not a JSON object or array"),
    ('{"verdicts": []}', "no `results` list"), ('[{"rule_id": "R17"', "not JSON"),
])
def test_other_shapes_stay_malformed(stub_llm, content, message):
    """A scalar is rejected as such (a clean LlmMalformed, never an AttributeError from the client)."""
    from investwatch_analytics.llm.client import LlmMalformed

    stub_llm.script.append(Reply(content=content))
    try:
        client(stub_llm).complete("s", "u")
        err = None
    except Exception as exc:  # noqa: BLE001 - the type is the assertion
        err = exc
    assert isinstance(err, LlmMalformed) and message in str(err), repr(err)
