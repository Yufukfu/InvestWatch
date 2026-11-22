"""HttpJudge: validation, quote verification, chunk merge, failure paths (analytics-llm-p0 task group 7).

Only the local stub server is called.
"""

from __future__ import annotations

import json
import logging

import pytest

from conftest import stored_hash
from llm_stub import Reply, closed_port_url
from investwatch_analytics.config import LlmSettings
from investwatch_analytics.llm.judge import SemanticCheck
from investwatch_analytics.preprocessing import preprocess

ALFA = (
    "Konto Premium Alfa Inwestycje. Zarabiaj nawet do 18% rocznie na portfelu ETF! "
    "Dołącz do 50 000 zadowolonych inwestorów. Działamy pod nadzorem KNF – Twoje środki są bezpieczne. "
    "Otwórz konto w 5 minut. *Inwestowanie wiąże się z ryzykiem utraty części lub całości kapitału."
)
KNF = "Działamy pod nadzorem KNF – Twoje środki są bezpieczne."
R17 = SemanticCheck("R17", "Czy odwołanie do KNF sugeruje aprobatę produktu?", ("fail", "pass", "uncertain"))
R18 = SemanticCheck("R18", "Czy nadzór jest argumentem bezpieczeństwa?", ("fail", "pass", "uncertain"))


def judge_for(url: str, **env):
    from investwatch_analytics.llm.judge import HttpJudge

    return HttpJudge(LlmSettings.from_env({"LLM_BASE_URL": url, "LLM_MODEL": "gemma3:4b", **env}))


def ask(judge, text=ALFA, checks=(R17,), module="M2"):
    pre = preprocess(text)
    return judge.judge(module=module, module_context="", text=text, content_hash=stored_hash(text),
                       sentences=pre.sentences, checks=list(checks))


def item(rule_id="R17", result="fail", quote=KNF, explanation="Sugeruje aprobatę."):
    return {"rule_id": rule_id, "result": result, "evidence_quote": quote, "explanation": explanation}


# ---- happy path and request ---------------------------------------------------------------------


def test_valid_verdict(stub_llm):
    stub_llm.script.append(Reply.results(item()))
    out = ask(judge_for(stub_llm.base_url))
    assert out.status == "ok" and out.model == "gemma3:4b"
    v = out.verdicts["R17"]
    assert v.result == "fail" and v.evidence == KNF and v.evidence in ALFA and v.explanation == "Sugeruje aprobatę."


def test_request_carries_one_document_block_and_the_checks(stub_llm):
    ask(judge_for(stub_llm.base_url), checks=(R17, R18))
    [req] = stub_llm.requests
    system, user = (m["content"] for m in req["body"]["messages"])
    assert user.startswith("<document>\n") and user.endswith("\n</document>") and KNF in user
    assert "R17" in system and "R18" in system and KNF not in system


def test_no_checks_no_call(stub_llm):
    out = ask(judge_for(stub_llm.base_url), checks=())
    assert out.status == "nothing_to_ask" and out.verdicts == {} and stub_llm.requests == []


# ---- validation --------------------------------------------------------------------------------------


def test_hallucinated_quote_becomes_uncertain(stub_llm):
    stub_llm.script.append(Reply.results(item(quote="Produkt zatwierdzony przez KNF")))
    v = ask(judge_for(stub_llm.base_url)).verdicts["R17"]
    assert v.result == "uncertain" and v.evidence is None and "cytat" in v.explanation.lower()


def test_trivial_quote_becomes_uncertain(stub_llm):
    stub_llm.script.append(Reply.results(item(quote="KNF")))
    v = ask(judge_for(stub_llm.base_url)).verdicts["R17"]
    assert v.result == "uncertain" and v.evidence is None


def test_eight_char_quote_is_enough(stub_llm):
    stub_llm.script.append(Reply.results(item(quote="nadzorem")))
    v = ask(judge_for(stub_llm.base_url)).verdicts["R17"]
    assert v.result == "fail" and v.evidence == "nadzorem"


def test_fail_without_quote_becomes_uncertain(stub_llm):
    stub_llm.script.append(Reply.results(item(quote=None)))
    v = ask(judge_for(stub_llm.base_url)).verdicts["R17"]
    assert v.result == "uncertain" and v.evidence is None


def test_pass_without_quote_is_kept(stub_llm):
    stub_llm.script.append(Reply.results(item("R18", "pass", None, "Brak powiązania.")))
    v = ask(judge_for(stub_llm.base_url), checks=(R18,)).verdicts["R18"]
    assert v.result == "pass" and v.evidence is None and v.explanation == "Brak powiązania."


def test_pass_with_bad_quote_becomes_uncertain(stub_llm):
    stub_llm.script.append(Reply.results(item("R18", "pass", "Tego zdania nie ma w tekście.")))
    assert ask(judge_for(stub_llm.base_url), checks=(R18,)).verdicts["R18"].result == "uncertain"


def test_whitespace_insensitive_quote_maps_to_original_span(stub_llm):
    text = "Działamy pod\n nadzorem   KNF – Twoje środki są bezpieczne."
    stub_llm.script.append(Reply.results(item(quote="Działamy pod nadzorem KNF")))
    v = ask(judge_for(stub_llm.base_url), text=text).verdicts["R17"]
    assert v.evidence == "Działamy pod\n nadzorem   KNF" and v.evidence in text


@pytest.mark.parametrize("bad", [
    item(result="maybe"),
    item(result="not_applicable"),                       # not in R17's allowed results
    {**item(), "explanation": "x" * 501},
    {**item(), "explanation": 5},
    {**item(), "evidence_quote": "y" * 401},
    {**item(), "evidence_quote": ["a"]},
    {"rule_id": "R17"},
    "R17 fail",
])
def test_invalid_item_is_dropped(stub_llm, bad):
    stub_llm.script.append(Reply(content=json.dumps({"results": [bad]})))
    out = ask(judge_for(stub_llm.base_url))
    assert out.verdicts == {} and out.status == "ok"


def test_unrequested_rule_id_is_dropped(stub_llm):
    stub_llm.script.append(Reply.results(item(), item("R2", "pass", None)))
    assert set(ask(judge_for(stub_llm.base_url)).verdicts) == {"R17"}


def test_duplicate_keeps_the_first(stub_llm):
    stub_llm.script.append(Reply.results(item(result="pass", quote=None), item()))
    assert ask(judge_for(stub_llm.base_url)).verdicts["R17"].result == "pass"


def test_control_characters_are_stripped_from_explanations(stub_llm):
    stub_llm.script.append(Reply.results(item(explanation="Linia\x00 druga\x1b[31m‮")))
    v = ask(judge_for(stub_llm.base_url)).verdicts["R17"]
    assert "\x00" not in v.explanation and "\x1b" not in v.explanation and "‮" not in v.explanation


def test_quote_must_come_from_the_chunk_sent(stub_llm):
    # The quote is in the document but in a chunk other than the one that answered.
    tail = " ".join(f"Neutralne zdanie numer {i:03d} o ofercie banku." for i in range(60))
    text = f"{KNF} {tail}"
    stub_llm.script.append(Reply.results(item(result="pass", quote=None)))          # chunk 1
    stub_llm.script.extend(Reply.results(item(quote=KNF)) for _ in range(10))       # later chunks quote chunk 1
    out = ask(judge_for(stub_llm.base_url, LLM_CHUNK_CHARS="600", LLM_MAX_CHUNKS="20"), text=text)
    assert out.verdicts["R17"].result == "uncertain"


# ---- chunks -----------------------------------------------------------------------------------------


def long_text_with(knf_at_end: bool) -> str:
    tail = " ".join(f"Neutralne zdanie numer {i:03d} o ofercie banku." for i in range(40))
    return f"{tail} {KNF}" if knf_at_end else f"{KNF} {tail}"


def test_worst_chunk_wins(stub_llm):
    text = long_text_with(knf_at_end=True)
    stub_llm.default = Reply.results(item(result="fail"))
    stub_llm.script.append(Reply.results(item(result="pass", quote=None)))
    out = ask(judge_for(stub_llm.base_url, LLM_CHUNK_CHARS="900"), text=text)
    assert len(stub_llm.requests) > 1
    assert out.verdicts["R17"].result == "fail" and out.verdicts["R17"].evidence == KNF


def test_tie_goes_to_the_earliest_chunk(stub_llm):
    text = long_text_with(knf_at_end=True)
    stub_llm.script.append(Reply.results(item(result="pass", quote=None, explanation="pierwszy")))
    stub_llm.default = Reply.results(item(result="pass", quote=None, explanation="późniejszy"))
    out = ask(judge_for(stub_llm.base_url, LLM_CHUNK_CHARS="900"), text=text)
    assert out.verdicts["R17"].explanation == "pierwszy"


def test_one_failed_chunk_drops_the_module(stub_llm):
    text = long_text_with(knf_at_end=True)
    stub_llm.script.append(Reply.results(item()))
    stub_llm.default = Reply(status=500)
    out = ask(judge_for(stub_llm.base_url, LLM_CHUNK_CHARS="900"), text=text)
    assert out.verdicts == {} and out.status == "unavailable" and out.model is None


def test_truncation_is_logged(stub_llm, caplog):
    caplog.set_level(logging.INFO)
    text = long_text_with(knf_at_end=False)
    ask(judge_for(stub_llm.base_url, LLM_CHUNK_CHARS="300", LLM_MAX_CHUNKS="2"), text=text)
    assert len(stub_llm.requests) == 2
    assert any(getattr(r, "reason", None) == "llm_truncated" for r in caplog.records)


def test_short_text_is_one_request_per_call(stub_llm):
    ask(judge_for(stub_llm.base_url), checks=(R17, R18))
    assert len(stub_llm.requests) == 1


# ---- failures ----------------------------------------------------------------------------------------


@pytest.mark.parametrize("reply, status, reason", [
    (Reply(status=500), "unavailable", "llm_unavailable"),
    (Reply(content='{"results": [{"rule_id": "R17", "result": "fail"'), "malformed", "llm_malformed"),
    (Reply(content='"R17 fail"'), "malformed", "llm_malformed"),  # a bare array is accepted (analytics-llm-bare-array)
])
def test_failures_degrade(stub_llm, caplog, reply, status, reason):
    caplog.set_level(logging.INFO)
    stub_llm.script.append(reply)
    out = ask(judge_for(stub_llm.base_url))
    assert out.verdicts == {} and out.status == status and out.model is None
    assert any(getattr(r, "reason", None) == reason for r in caplog.records)
    assert all(ALFA[:40] not in f"{r.getMessage()} {r.__dict__}" for r in caplog.records)


def test_llm_down():
    out = ask(judge_for(closed_port_url()))
    assert out.verdicts == {} and out.status == "unavailable"


def test_timeout(stub_llm, caplog):
    caplog.set_level(logging.INFO)
    stub_llm.script.append(Reply(sleep_s=2))
    out = ask(judge_for(stub_llm.base_url, LLM_TIMEOUT_S="0.4"))
    assert out.status == "unavailable" and any(getattr(r, "reason", None) == "llm_timeout" for r in caplog.records)


def test_judge_never_raises_on_unexpected_content(stub_llm):
    stub_llm.script.append(Reply(content=json.dumps({"results": [None, 1, [], {"rule_id": None}]})))
    out = ask(judge_for(stub_llm.base_url))
    assert out.verdicts == {} and out.status == "ok" and out.model is None  # no verdict used, so no model to report


# ---- group 7 review fixes ----------------------------------------------------------------------------


def test_fallback_escapes_regex_metacharacters(stub_llm):
    text = "Zarabiaj do  zysk (18%)\n+ [ETF] rocznie."
    stub_llm.script.append(Reply.results(item(quote="zysk (18%) + [ETF]")))
    v = ask(judge_for(stub_llm.base_url), text=text).verdicts["R17"]
    assert v.result == "fail" and v.evidence == "zysk (18%)\n+ [ETF]"


@pytest.mark.parametrize("quote", ["   ", "", "\n\t"])
def test_blank_quote_counts_as_no_quote(stub_llm, quote):
    stub_llm.script.append(Reply.results(item("R18", "pass", quote, "Brak powiązania.")))
    v = ask(judge_for(stub_llm.base_url), checks=(R18,)).verdicts["R18"]
    assert v.result == "pass" and v.evidence is None


def test_padded_quote_is_stripped(stub_llm):
    stub_llm.script.append(Reply.results(item(quote=f"  {KNF}  ")))
    assert ask(judge_for(stub_llm.base_url)).verdicts["R17"].evidence == KNF


def test_exact_match_is_preferred_over_the_fallback(stub_llm):
    text = f"Działamy pod  nadzorem KNF – Twoje środki są bezpieczne. {KNF}"  # the near-variant comes first
    stub_llm.script.append(Reply.results(item(quote=KNF)))
    v = ask(judge_for(stub_llm.base_url), text=text).verdicts["R17"]
    assert v.evidence == KNF


def test_fallback_match_far_longer_than_the_quote_is_rejected(stub_llm):
    text = "Działamy pod" + " " * 5000 + "nadzorem KNF."
    stub_llm.script.append(Reply.results(item(quote="Działamy pod nadzorem KNF")))
    v = ask(judge_for(stub_llm.base_url), text=text).verdicts["R17"]
    assert v.result == "uncertain" and v.evidence is None


def test_empty_explanation_after_cleaning_gets_a_fixed_text(stub_llm):
    stub_llm.script.append(Reply.results(item(explanation="\x00‮")))
    v = ask(judge_for(stub_llm.base_url)).verdicts["R17"]
    assert v.result == "fail" and v.explanation.strip()


def test_padding_does_not_bypass_the_minimum_length(stub_llm):
    stub_llm.script.append(Reply.results(item(quote="  KNF   ")))  # 8 chars only with the padding
    v = ask(judge_for(stub_llm.base_url)).verdicts["R17"]
    assert v.result == "uncertain" and v.evidence is None
