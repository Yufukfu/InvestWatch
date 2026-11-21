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


def test_no_embedder_vocabulary_still_passes():
    assert gate("Kupiłem obligacje skarbowe").passed


def test_embedder_name_is_carried_for_the_log():
    d = evaluate("Przepis", source_kind="third_party", firm_matched=False, terms=TERMS, settings=ON,
                 embedder="bge-m3")
    assert d.log_extra()["embedder"] == "bge-m3"


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
                                  "Etos i ethos pracy", "Nowe buty Nike",
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


@pytest.mark.parametrize("text", ["1 " * 1_000_000, " ." * 1_000_000, "za " * 700_000,
                                  "przepis na sernik " * 120_000], ids=["digits", "dots", "prefix", "prose"])
def test_large_hostile_text_is_fast(text):
    norm = normalize(text)  # preprocessing normalizes once; only the gate is timed
    started = time.perf_counter()
    evaluate(norm, source_kind="third_party", firm_matched=False, terms=TERMS, settings=ON)
    assert time.perf_counter() - started < 3.0


def test_only_the_start_is_scanned():
    from investwatch_analytics.gate import MAX_GATE_CHARS

    assert not gate("a " * (MAX_GATE_CHARS // 2) + "zysk").passed
    assert gate("a " * (MAX_GATE_CHARS // 2 - 3) + "zysk").passed


def test_decision_is_frozen():
    with pytest.raises(Exception):
        gate("zysk").passed = False  # type: ignore[misc]
    assert isinstance(gate("zysk"), GateDecision)


# ---- review fixes (group 4) -------------------------------------------------------------------


@pytest.mark.parametrize("text", [
    "Handluję na forexie od 5 lat", "Hossa na Nasdaqu", "Najlepsze CFDs w tym roku", "Top ETFs for 2026",
    "S&P500 na nowym szczycie", "Kurs BTCUSD rośnie", "Tradujesz dziś złoto?", "Tradowanie na złocie",
    "Wolność finansowa w 3 lata", "Pasywny dochód co miesiąc", "WIG20 traci 2%", "Notowania GPW na żywo",
    "Kupuję ETH i USDT", "Kurs EUR/USD i waluty", "Ulokuj pieniądze bezpiecznie", "Pomnażaj swoje pieniądze",
    "Spółki z NewConnect lecą w górę", "Zrób 10x na altcoinach", "Kopiuj moje transakcje",
    "returns 20% monthly", "passive income daily", "#forexsignals #forextrader", "#etfinvesting",
], ids=lambda t: t[:24])
def test_common_investment_posts_pass(text):
    assert gate(text).passed, text


def test_wy_prefix():
    assert gate("Całość już wyinwestowana").passed


def test_unknown_key_rejected(tmp_path):
    with pytest.raises(GateTermsError, match="prefix"):
        load_terms(write(tmp_path, {**VALID, "prefix": ["za"]}))


def test_bare_star_word_in_phrase_rejected(tmp_path):
    with pytest.raises(GateTermsError, match="terms"):
        load_terms(write(tmp_path, {**VALID, "terms": ["stop *"]}))


def test_terms_and_prefixes_with_diacritics_or_uppercase(tmp_path):
    t = load_terms(write(tmp_path, {**VALID, "terms": ["Giełd*", "Złoto"], "prefixes": ["ZA", "Pó"]}))
    ev = lambda s: evaluate(s, source_kind="third_party", firm_matched=False, terms=t, settings=ON).passed
    assert ev("gielda") and ev("ZŁOTO") and ev("zagieldowy") and ev("pogieldowy")
