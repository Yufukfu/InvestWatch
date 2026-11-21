"""Investment topic gate, dictionary part (analytics-embeddings task group 4). Pure: no I/O, no model."""

from __future__ import annotations

import time

import pytest
import yaml

from investwatch_analytics.config import GateSettings
from investwatch_analytics.gate import (
    GateDecision,
    GateTermsError,
    evaluate,
    load_terms,
    strip_diacritics,
)
from investwatch_analytics.preprocessing import normalize

TERMS = load_terms()
ON = GateSettings()


def gate(text, source_kind="third_party", firm_matched=False, settings=ON):
    return evaluate(normalize(text), source_kind=source_kind, firm_matched=firm_matched, terms=TERMS,
                    settings=settings)


# ---- normalization ----------------------------------------------------------------------------


def test_strip_diacritics_handles_polish_l():
    assert strip_diacritics("Zażółć gęślą jaźń ŁÓDŹ") == "zazolc gesla jazn lodz"


# ---- passes on the dictionary -----------------------------------------------------------------


def test_investment_post_passes():
    d = gate("Zainwestuj w CFD na forex, zyski 20% miesięcznie")
    assert d.passed and d.reason == "dictionary" and d.dict_hits >= 3


def test_post_without_diacritics_passes():
    assert gate("gielda i kryptowaluty, moje zyski z inwestycji").passed


@pytest.mark.parametrize("text", [
    "Ile zysków w tym roku?", "Bez zyskow nie ma zabawy", "Zainwestuj dziś!", "Pomnóż oszczędności",
    "Stopa zwrotu 12%", "stopy zwrotu bywają różne", "Kup akcje spółki", "obligacje skarbowe",
    "Nowy fundusz ETF", "ETF-y na S&P", "Twój portfel kryptowalut", "Konto maklerskie", "Giełda dziś",
    "Sygnały tradingowe", "dźwignia 1:500", "Bitcoin po 100k", "Lokata 7%", "dywidenda wypłacona",
    "Invest now", "crypto signals", "stock market", "broker account", "forex", "CFD",
], ids=lambda t: t[:20])
def test_inflected_and_mixed_language_terms(text):
    assert gate(text).passed, text


def test_etf_alone_passes():
    assert gate("Kupuję ETF").passed


def test_phrase_across_raw_whitespace():
    d = evaluate("stopa\n\t zwrotu", source_kind="third_party", firm_matched=False, terms=TERMS, settings=ON)
    assert d.passed and d.dict_hits == 1


def test_embedder_down_vocabulary_still_passes():
    d = gate("Kupiłem obligacje skarbowe")
    assert d.passed and d.similarity is None and d.embedder is None


def test_registry_firm_match_counts_as_a_hit():
    d = gate("Spotkanie z zespołem Alfa w piątek", firm_matched=True)
    assert d.passed and d.dict_hits == 1


def test_hits_are_counted():
    assert gate("zysk zysk zysk").dict_hits == 3
    assert gate("zysk", firm_matched=True).dict_hits == 2


# ---- drops ------------------------------------------------------------------------------------


def test_recipe_dropped_with_reason():
    d = gate("Przepis na sernik babci: twaróg, jajka, cukier i masło. Piec 60 minut.")
    assert not d.passed and d.reason == "off_topic" and d.dict_hits == 0
    assert d.similarity is None and d.embedder is None


@pytest.mark.parametrize("text", ["ketfon to nowy telefon", "netflix i chill", "Uwielbiam koty",
                                  "Targi forexpo w Poznaniu", "cfdx model",
                                  "Mecz Legii w niedzielę", "tradycja świąt"])
def test_term_inside_another_word_or_unrelated_text_dropped(text):
    assert not gate(text).passed, text


def test_unknown_source_kind_is_gated():
    assert not gate("Mecz Legii w niedzielę o 18:00", source_kind="unknown").passed
    assert gate("sygnały forex na dziś", source_kind="unknown").passed


# ---- bypass and switch ------------------------------------------------------------------------


def test_firm_page_bypasses():
    d = gate("Kontakt: ul. Prosta 1, Warszawa", source_kind="firm_own")
    assert d.passed and d.reason == "bypassed_firm_own"


def test_gate_disabled_drops_nothing():
    d = gate("Przepis na sernik", settings=GateSettings(enabled=False))
    assert d.passed and d.reason == "gate_disabled"


# ---- log fields -------------------------------------------------------------------------------


def test_log_fields_have_figures_and_no_text():
    d = gate("Przepis na sernik babci")
    extra = d.log_extra()
    assert extra == {"reason": "off_topic", "dict_hits": 0, "similarity": None, "embedder": None}
    assert "sernik" not in repr(extra)


# ---- terms file -------------------------------------------------------------------------------


def write(tmp_path, data) -> str:
    p = tmp_path / "gate_terms.yaml"
    p.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return str(p)


VALID = {"version": 1, "terms": ["zysk*"], "prefixes": ["za"], "centroids": {"offer": ["Zarabiaj"]}}


def test_valid_custom_file(tmp_path):
    t = load_terms(write(tmp_path, VALID))
    assert evaluate("zazysk", source_kind="third_party", firm_matched=False, terms=t, settings=ON).passed


@pytest.mark.parametrize("data,key", [
    ({**VALID, "terms": []}, "terms"),
    ({**VALID, "terms": ["zysk*", ""]}, "terms"),
    ({**VALID, "terms": ["*"]}, "terms"),
    ({**VALID, "terms": "zysk"}, "terms"),
    ({**VALID, "prefixes": [1]}, "prefixes"),
    ({**VALID, "centroids": {"offer": []}}, "offer"),
    ({**VALID, "centroids": ["x"]}, "centroids"),
    ({**VALID, "version": 2}, "version"),
    ({k: v for k, v in VALID.items() if k != "terms"}, "terms"),
], ids=["empty", "blank-term", "star-only", "not-list", "bad-prefix", "empty-class", "centroids-list",
        "version", "missing"])
def test_invalid_file_names_file_and_key(tmp_path, data, key):
    path = write(tmp_path, data)
    with pytest.raises(GateTermsError) as exc:
        load_terms(path)
    assert key in str(exc.value) and "gate_terms.yaml" in str(exc.value)


def test_regex_characters_in_terms_are_literal(tmp_path):
    t = load_terms(write(tmp_path, {**VALID, "terms": ["s&p", "a.b"]}))
    ev = lambda s: evaluate(s, source_kind="third_party", firm_matched=False, terms=t, settings=ON).passed
    assert ev("indeks s&p 500") and not ev("axb")


def test_shipped_file_has_centroid_seeds():
    assert TERMS.centroids and all(TERMS.centroids.values())


# ---- performance ------------------------------------------------------------------------------


def test_large_hostile_text_is_fast():
    text = ("zyskzyskzysk " * 50_000) + ("a" * 200_000) + (" ." * 100_000)
    started = time.perf_counter()
    gate(text)
    assert time.perf_counter() - started < 2.0


def test_decision_is_frozen():
    with pytest.raises(Exception):
        gate("zysk").passed = False  # type: ignore[misc]
    assert isinstance(gate("zysk"), GateDecision)
