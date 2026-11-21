"""M3 signals, S3.4 gate, attribution and finding (change analytics-m1-m3, task group 4)."""

from __future__ import annotations

from pathlib import Path

import pytest

from conftest import NOW, make_doc
from investwatch_analytics.models import Finding, RuleResult, ScrapedDocument
from investwatch_analytics.modules import m3
from investwatch_analytics.modules.advertiser import build_advertiser
from investwatch_analytics.preprocessing import preprocess
from investwatch_analytics.registry import Registry
from investwatch_analytics.rules import engine
from investwatch_analytics.rules.engine import Catalogue, Context, run_rules

SEED = Path(__file__).resolve().parents[1] / "registry" / "seed.csv"
GOLD = "007bbcee-0737-5c6d-b9b4-ce56fcbfa8e4"
VIP = "cdbf5306-1bb9-5d3b-b8b8-bc64f2ed8e88"
BLOG = "72acbb3b-3546-5c9b-9b26-2b29f69ccce9"
KASIA = "182e5a42-1041-5147-99dc-84d73ed34220"


@pytest.fixture(scope="module")
def registry() -> Registry:
    return Registry.from_csv(SEED)


@pytest.fixture(scope="module")
def cat() -> Catalogue:
    return Catalogue.load_module("M3")


def page(text: str, **kw) -> ScrapedDocument:
    base = {"source_kind": "unknown", "platform": "web", "url": "https://oferta.example.com/a", "text": text}
    base.update(kw)
    return ScrapedDocument.model_validate(make_doc(**base))


def ctx_of(doc: ScrapedDocument, registry: Registry) -> Context:
    match = registry.match(doc.text, doc.url) or registry.match_links(doc.links)
    return Context(doc=doc, pre=preprocess(doc.text), firm_match=match, registry=registry)


def signals(doc, registry, cat) -> dict:
    return {r.rule_id: r for r in run_rules(cat, ctx_of(doc, registry))}


def finding(doc, registry, cat) -> Finding:
    return m3.build_finding(ctx_of(doc, registry), cat, advertiser=build_advertiser(doc, registry), now=NOW)


@pytest.fixture
def mock(mock_documents):
    by_id = {d["id"]: d for d in mock_documents}
    return lambda doc_id: ScrapedDocument.model_validate(by_id[doc_id])


def rr(rule_id: str, result: str) -> RuleResult:
    return RuleResult(rule_id=rule_id, name="x", result=result, severity="high", method="rule")


# ---- catalogue and semantics -------------------------------------------------------------------


def test_m3_implemented(cat):
    assert [s.id for s in cat.implemented] == ["S3.1", "S3.2", "S3.3", "S3.4", "S3.5", "S3.6", "S3.8"]


def test_rules_only_candidates(mock, registry, cat):
    s = signals(mock(GOLD), registry, cat)
    assert s["S3.3"].result == "uncertain" and s["S3.3"].evidence in mock(GOLD).text
    assert s["S3.4"].result == "uncertain" and s["S3.4"].evidence in mock(GOLD).text
    assert "S3.7" not in s


# ---- S3.1 --------------------------------------------------------------------------------------


def test_s31_handle(mock, registry, cat):
    r = signals(mock(VIP), registry, cat)["S3.1"]
    assert (r.result, r.evidence) == ("fail", "@sygnaly_vip")


def test_s31_page_host(mock, registry, cat):
    r = signals(mock(GOLD), registry, cat)["S3.1"]
    assert (r.result, r.evidence) == ("fail", "zlotykapital-fo.example.com") and "adres" in r.explanation


def test_s31_author_name(registry, cat):
    r = signals(page("x", author={"name": "Kasa Plus"}), registry, cat)["S3.1"]
    assert (r.result, r.evidence) == ("fail", "Kasa Plus")


# ---- S3.2 --------------------------------------------------------------------------------------


def test_s32_family_office(mock, registry, cat):
    r = signals(mock(GOLD), registry, cat)["S3.2"]
    assert (r.result, r.evidence) == ("fail", "Family Office")


def test_s32_none(mock, registry, cat):
    assert signals(mock(VIP), registry, cat)["S3.2"].result == "pass"


# ---- S3.3 --------------------------------------------------------------------------------------


def test_s33_personal(mock, registry, cat):
    r = signals(mock(GOLD), registry, cat)["S3.3"]
    assert r.result == "uncertain" and r.evidence in ("konsultacji 1:1", "dopasujemy portfel do Twojej sytuacji")


def test_s33_szyty_na_miare(registry, cat):
    r = signals(page("Portfel szyty na miarę Twoich celów."), registry, cat)["S3.3"]
    assert (r.result, r.evidence) == ("uncertain", "szyty na miarę")


def test_s33_mass(mock, registry, cat):
    assert signals(mock(VIP), registry, cat)["S3.3"].result == "pass"


# ---- S3.4 --------------------------------------------------------------------------------------


def test_s34_buy_sell(mock, registry, cat):
    r = signals(mock(GOLD), registry, cat)["S3.4"]
    assert r.result == "uncertain" and "rekomendujemy kupno obligacji" in r.evidence


def test_s34_instrument_in_previous_sentence(mock, registry, cat):
    r = signals(mock(VIP), registry, cat)["S3.4"]
    assert (r.result, r.evidence) == ("uncertain", "Codziennie mówię, co kupić, a co sprzedać.")


def test_s34_instrument_two_sentences_away(registry, cat):
    r = signals(page("Mamy akcje. Pogoda jest ładna. Co kupić? Napisz."), registry, cat)["S3.4"]
    assert r.result == "pass"


def test_s34_negated(mock, registry, cat):
    assert signals(mock(BLOG), registry, cat)["S3.4"].result == "pass"


def test_s34_negated_verb(registry, cat):
    assert signals(page("Nie polecamy kupna akcji spółek z WIG20."), registry, cat)["S3.4"].result == "pass"


def test_s34_personal_story(mock, registry, cat):
    assert signals(mock(KASIA), registry, cat)["S3.4"].result == "pass"


def test_s34_plain_crypto(registry, cat):
    assert signals(page("Kupuj bitcoina teraz, sprzedaj na szczycie."), registry, cat)["S3.4"].result == "pass"


def test_s34_crypto_derivative(registry, cat):
    r = signals(page("Kupuj CFD na bitcoina, zanim wystrzeli."), registry, cat)["S3.4"]
    assert (r.result, r.evidence) == ("uncertain", "Kupuj CFD na bitcoina, zanim wystrzeli.")


# ---- S3.5 / S3.6 / S3.8 ------------------------------------------------------------------------


def test_s35_subscription(mock, registry, cat):
    r = signals(mock(GOLD), registry, cat)["S3.5"]
    assert r.result == "fail" and r.evidence in "Abonament 990 zł miesięcznie"


def test_s35_monthly_price(mock, registry, cat):
    assert signals(mock(VIP), registry, cat)["S3.5"].result == "fail"


def test_s35_free(mock, registry, cat):
    assert signals(mock(BLOG), registry, cat)["S3.5"].result == "pass"


def test_s36_zloty(mock, registry, cat):
    r = signals(mock(GOLD), registry, cat)["S3.6"]
    assert r.result == "fail" and "zł" in r.evidence


def test_s36_language_only(mock, registry, cat):
    assert (signals(mock(BLOG), registry, cat)["S3.6"].result, signals(mock(BLOG), registry, cat)["S3.6"].evidence) == (
        "fail", None)


def test_s36_english_abroad(registry, cat):
    d = page("We manage portfolios for wealthy families worldwide.", url="https://fo.example.com/")
    assert signals(d, registry, cat)["S3.6"].result == "pass"


def test_s38_crypto_group(registry, cat):
    d = page("Kupuj bitcoina teraz, sprzedaj na szczycie. Grupa VIP 99 zł/mies.", platform="instagram",
             url="https://www.instagram.com/p/C1/", source_kind="third_party", author={"handle": "@krypto_ola"})
    f = finding(d, registry, cat)
    s = {r.rule_id: r for r in f.rules}
    assert s["S3.8"].result == "fail" and s["S3.8"].evidence == "Kupuj bitcoina teraz, sprzedaj na szczycie."
    assert "poza art. 2" in s["S3.8"].explanation and s["S3.4"].result == "pass"
    assert f.score <= 0.4 and "nie są wymienione w katalogu z art. 2 u.o.i.f. (załącznik do tematu 3)" in f.summary


def test_s38_derivative_is_not_crypto(registry, cat):
    assert signals(page("Kupuj CFD na bitcoina, zanim wystrzeli."), registry, cat)["S3.8"].result == "pass"


def test_s38_negated(registry, cat):
    assert signals(page("Nie polecamy kupna bitcoina."), registry, cat)["S3.8"].result == "pass"


# ---- score and gate ----------------------------------------------------------------------------


def test_gold_score(mock, registry, cat):
    assert finding(mock(GOLD), registry, cat).score >= 0.7


BASE = [("S3.1", "fail"), ("S3.2", "pass"), ("S3.5", "pass"), ("S3.6", "fail"), ("S3.8", "pass")]


def score_of(cat, **results) -> tuple[float, bool]:
    rules = [rr(i, r) for i, r in BASE] + [rr(i.replace("_", "."), r) for i, r in results.items()]
    return m3.score(rules, cat)


def test_instrument_recommendation_alone_is_strong(cat):
    s, capped = score_of(cat, S3_3="pass", S3_4="fail")
    assert s >= 0.7 and not capped


def test_personalisation_alone_is_weak(cat):
    s, capped = score_of(cat, S3_3="fail", S3_4="pass")
    assert s <= 0.4 and capped


def test_both_elements_strongest(cat):
    assert score_of(cat, S3_3="fail", S3_4="fail")[0] > score_of(cat, S3_3="pass", S3_4="fail")[0]


def test_uncertain_s34_lifts_gate(cat):
    assert score_of(cat, S3_3="pass", S3_4="uncertain")[1] is False


def test_gate_caps_strong_non_advisory(cat):
    rules = [rr("S3.1", "fail"), rr("S3.2", "fail"), rr("S3.5", "fail"), rr("S3.6", "fail"),
             rr("S3.3", "pass"), rr("S3.4", "pass")]
    from investwatch_analytics.rules.scoring import sigmoid_score

    s, capped = m3.score(rules, cat)
    assert capped and s == min(sigmoid_score(rules, cat), 0.4) and sigmoid_score(rules, cat) > 0.4


def test_gate_summary(registry, cat):
    d = page("Family office i zarządzanie portfelem. Abonament 500 zł miesięcznie.")
    f = finding(d, registry, cat)
    assert f.score <= 0.4 and "0,4" in f.summary


def test_educational_capped(mock, registry, cat):
    assert finding(mock(BLOG), registry, cat).score <= 0.4


def test_mass_signals_without_llm(mock, registry, cat):
    rules_only = finding(mock(VIP), registry, cat).score
    confirmed = [r if r.rule_id != "S3.4" else r.model_copy(update={"result": "fail"})
                 for r in finding(mock(VIP), registry, cat).rules]
    assert 0.4 < rules_only < m3.score(confirmed, cat)[0]


# ---- advisory signals and attribution ----------------------------------------------------------


def test_has_advisory():
    assert not m3.has_advisory([rr("S3.1", "fail"), rr("S3.6", "fail"), rr("S3.2", "pass")])
    for sid in ("S3.2", "S3.3", "S3.4", "S3.5", "S3.8"):
        assert m3.has_advisory([rr("S3.1", "fail"), rr(sid, "uncertain")])
    assert not m3.has_advisory([rr("S3.2", "not_applicable")])


def _attr(text: str, registry, cat) -> bool:
    d = page(text, source_kind="third_party", platform="instagram", url="https://www.instagram.com/p/A1/",
             author={"handle": "@trader_ola"})
    ctx = ctx_of(d, registry)
    return m3.offer_is_publishers(ctx, run_rules(cat, ctx), cat)


def test_finfluencer_own_buy_calls(registry, cat):
    assert _attr("Konto mam w EuroTrade Markets. Moja grupa: co tydzień mówię, co kupić z akcji WIG20.", registry, cat)


def test_firms_own_offer(registry, cat):
    assert not _attr("Alfa Inwestycje DM rekomenduje kupno obligacji skarbowych.", registry, cat)


def test_no_advisory_no_offer(mock, registry, cat):
    for doc_id in ("3c41441c-40ba-5864-b3e0-03f8bc9acebe", KASIA):
        ctx = ctx_of(mock(doc_id), registry)
        assert not m3.offer_is_publishers(ctx, run_rules(cat, ctx), cat)


def test_personalisation_in_own_sentence(registry, cat):
    assert _attr("Polecam EuroTrade. Robię też konsultacje 1:1 dla obserwujących.", registry, cat)


# ---- finding -----------------------------------------------------------------------------------


def test_family_office_finding(mock, registry, cat, finding_validator):
    f = finding(mock(GOLD), registry, cat)
    assert f.module == "M3" and f.firm is None and f.advertiser.in_registry is False
    assert f.advertiser.on_warning_list is None and "zlotykapital-fo.example.com" in f.title
    assert f.content_excerpt and f.url == mock(GOLD).url and f.model.llm is None and "regułowy" in f.summary
    finding_validator.validate(f.to_contract())


def test_metadata_quotes_survive_the_safety_net(mock, registry, cat):
    for doc_id in (GOLD, VIP, BLOG):
        for r in finding(mock(doc_id), registry, cat).rules:
            assert "Nie udało się potwierdzić cytatu" not in (r.explanation or ""), r.rule_id


def test_s38_needs_a_crypto_word(registry, cat):
    assert signals(page("Kup teraz, zanim zniknie."), registry, cat)["S3.8"].result == "pass"


def test_s36_pl_host(registry, cat):
    d = page("Family office for wealthy families.", url="https://www.majatek-rodzinny.pl/oferta")
    r = signals(d, registry, cat)["S3.6"]
    assert (r.result, r.evidence) == ("fail", "majatek-rodzinny.pl")


# ---- group 4 review: false candidates, verb forms, negation scope, attribution over all candidates ----


@pytest.mark.parametrize("text", [
    "Kup kurs teraz! Akcja promocyjna do piątku.",
    "Kup dostęp do grupy. Opcja roczna taniej.",
    "Inwestorzy kupują akcje banków.",
    "Kup kurs i zdobądź certyfikat ukończenia.",
])
def test_s34_not_advice(registry, cat, text):
    assert signals(page(text), registry, cat)["S3.4"].result == "pass"


@pytest.mark.parametrize("text", [
    "Sprzedajcie akcje banków przed wynikami.",
    "Trzymajcie obligacje skarbowe do końca roku.",
    "Warto kupić akcje PKO teraz.",
    "Polecamy akcje PKO BP na ten kwartał.",
    "Zainwestuj w obligacje skarbowe teraz.",
    "Kupujcie opcje call na WIG20.",
])
def test_s34_recommending_forms(registry, cat, text):
    assert signals(page(text), registry, cat)["S3.4"].result == "uncertain"


def test_s34_negation_stops_at_comma(registry, cat):
    r = signals(page("Nie rekomendujemy kupna akcji X, ale kupuj ETF na S&P."), registry, cat)["S3.4"]
    assert r.result == "uncertain"


def test_s33_bare_questionnaire_is_not_personalisation(registry, cat):
    assert signals(page("Otwórz konto. Wypełnij ankietę i zacznij."), registry, cat)["S3.3"].result == "pass"


def test_s33_investment_questionnaire(registry, cat):
    assert signals(page("Wypełnij ankietę inwestycyjną, a dobierzemy portfel."), registry, cat)["S3.3"].result == "uncertain"


def test_attribution_checks_every_candidate(registry, cat):
    assert _attr("EuroTrade Markets rekomenduje kupno akcji PKO. Moja grupa VIP: co tydzień mówię, co kupić z akcji "
                 "WIG20.", registry, cat)


def test_broker_onboarding_is_not_the_publishers_offer(registry, cat):
    assert not _attr("Otwórz konto w EuroTrade Markets. Wypełnij ankietę i zacznij.", registry, cat)


# ---- review of #35, items 2 and 9: registry wording and legal bases ------------------------------------


def _real_registry(tmp_path) -> Registry:
    rows = SEED.read_text(encoding="utf-8").splitlines()
    out = [rows[0]] + [r.rstrip(",") + ",https://www.knf.gov.pl/podmioty" for r in rows[1:]]
    p = tmp_path / "knf.csv"
    p.write_text("\n".join(out) + "\n", encoding="utf-8")
    return Registry.from_csv(p)


def test_registry_demo_flag(registry, tmp_path):
    assert registry.demo is True and _real_registry(tmp_path).demo is False


def test_demo_registry_wording(mock, registry, cat):
    f = finding(mock(GOLD), registry, cat)
    s31 = {r.rule_id: r for r in f.rules}["S3.1"]
    for text in (s31.explanation, f.summary):
        assert "nie znaleziono w załadowanym rejestrze firm" in text and "(dane demonstracyjne)" in text
        assert "nie występuje" not in text and "KNF" not in text
    assert "spoza rejestru" not in f.title.lower()


def test_real_registry_wording(mock, tmp_path, cat):
    real = _real_registry(tmp_path)
    f = finding(mock(GOLD), real, cat)
    s31 = {r.rule_id: r for r in f.rules}["S3.1"]
    for text in (s31.explanation, f.summary):
        assert "nie znaleziono w załadowanym rejestrze firm" in text and "dane demonstracyjne" not in text


def test_legal_bases_are_sourced(cat):
    assert cat.get("S3.1").legal_basis is None
    assert cat.get("S3.3").legal_basis == cat.get("S3.4").legal_basis == "art. 76 u.o.i.f. (załącznik do tematu 3)"
    assert cat.get("S3.8").legal_basis == "art. 2 u.o.i.f. (załącznik do tematu 3)"
