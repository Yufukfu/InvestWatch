"""M1 signals and finding (change analytics-m1-m3, task group 3; specs/m1-third-party-signals)."""

from __future__ import annotations

from pathlib import Path

import pytest

from conftest import NOW, make_doc
from investwatch_analytics.models import Finding, ScrapedDocument
from investwatch_analytics.modules import m1
from investwatch_analytics.modules.advertiser import build_advertiser
from investwatch_analytics.preprocessing import preprocess
from investwatch_analytics.registry import Registry
from investwatch_analytics.rules import engine
from investwatch_analytics.rules.engine import Catalogue, Context, run_rules

SEED = Path(__file__).resolve().parents[1] / "registry" / "seed.csv"
JAN = "3c41441c-40ba-5864-b3e0-03f8bc9acebe"
KASIA = "182e5a42-1041-5147-99dc-84d73ed34220"
EURO = "2d7456b6-f7b5-52f2-a039-64e250001e24"


@pytest.fixture(scope="module")
def registry() -> Registry:
    return Registry.from_csv(SEED)


@pytest.fixture(scope="module")
def cat() -> Catalogue:
    return Catalogue.load_module("M1")


def third_party(**kw) -> ScrapedDocument:
    base = {"source_kind": "third_party", "platform": "instagram", "url": "https://www.instagram.com/p/T1/",
            "author": {"name": "Ola", "handle": "@ola_inwestuje"}}
    base.update(kw)
    return ScrapedDocument.model_validate(make_doc(**base))


def ctx_of(doc: ScrapedDocument, registry: Registry) -> Context:
    match = registry.match(doc.text, doc.url) or registry.match_links(doc.links)
    return Context(doc=doc, pre=preprocess(doc.text), firm_match=match, registry=registry)


def signals(doc, registry, cat) -> dict:
    return {r.rule_id: r for r in run_rules(cat, ctx_of(doc, registry))}


def finding(doc, registry, cat) -> Finding:
    ctx = ctx_of(doc, registry)
    return m1.build_finding(ctx, cat, advertiser=build_advertiser(doc, registry), now=NOW)


@pytest.fixture
def mock(mock_documents):
    by_id = {d["id"]: d for d in mock_documents}
    return lambda doc_id: ScrapedDocument.model_validate(by_id[doc_id])


# ---- catalogue ---------------------------------------------------------------------------------


def test_all_m1_signals_implemented(cat):
    assert [s.id for s in cat.implemented] == [f"S1.{i}" for i in range(1, 8)]


# ---- semantics, S1.5 ---------------------------------------------------------------------------


def test_rules_only_s15(mock, registry, cat):
    f = finding(mock(JAN), registry, cat)
    ids = [r.rule_id for r in f.rules]
    assert ids == [f"S1.{i}" for i in range(1, 8)]
    s15 = next(r for r in f.rules if r.rule_id == "S1.5")
    assert s15.result == "uncertain" and s15.evidence is None and "model" in s15.explanation
    assert "S1.5" in f.summary and "Nie sprawdzono" in f.summary


# ---- S1.1 --------------------------------------------------------------------------------------


def test_s11_name(mock, registry, cat):
    r = signals(mock(JAN), registry, cat)["S1.1"]
    assert (r.result, r.evidence) == ("fail", "EuroTrade Markets")


def test_s11_alias(mock, registry, cat):
    r = signals(mock(KASIA), registry, cat)["S1.1"]
    assert (r.result, r.evidence) == ("fail", "Alfa Inwestycje DM")


def test_s11_fuzzy_only(registry, cat):
    r = signals(third_party(text="Ostatnio chwalę Alfa Inwestycji za aplikację."), registry, cat)["S1.1"]
    assert (r.result, r.evidence) == ("uncertain", None)


def test_s11_link(registry, cat):
    href = "https://eurotrade-markets.example.com/pl/register?ref=X"
    r = signals(third_party(text="Polecam, link niżej.", links=[{"href": href}]), registry, cat)["S1.1"]
    assert (r.result, r.evidence) == ("fail", href) and "link" in r.explanation


def test_s11_no_firm_passes(registry, cat):
    assert signals(third_party(text="Nic o firmach."), registry, cat)["S1.1"].result == "pass"


# ---- S1.2 --------------------------------------------------------------------------------------


def test_s12_referral_link(mock, registry, cat):
    d = mock(JAN)
    r = signals(d, registry, cat)["S1.2"]
    assert r.result == "fail" and "ref=JAN500" in r.evidence and r.evidence in d.links[0].href
    assert "link" in r.explanation


@pytest.mark.parametrize("href", ["https://x.example.com/?AFF=12", "https://x.example.com/a?b=1&promo=W",
                                  "https://x.example.com/?referral=abc#top"])
def test_s12_other_keys(registry, cat, href):
    r = signals(third_party(text="Zobacz.", links=[{"href": href}]), registry, cat)["S1.2"]
    assert r.result == "fail" and r.evidence in href


def test_s12_key_in_path_is_not_a_referral(registry, cat):
    r = signals(third_party(text="Zobacz.", links=[{"href": "https://x.example.com/ref/abc"}]), registry, cat)
    assert r["S1.2"].result == "pass"


def test_s12_only_utm(registry, cat):
    href = "https://alfa-inwestycje.example.com/?utm_source=ig"
    r = signals(third_party(text="Zobacz.", links=[{"href": href}]), registry, cat)["S1.2"]
    assert r.result == "uncertain" and r.evidence in href


def test_s12_referral_beats_utm(registry, cat):
    links = [{"href": "https://a.example.com/?utm_source=ig"}, {"href": "https://a.example.com/?ref=Z"}]
    r = signals(third_party(text="Zobacz.", links=links), registry, cat)["S1.2"]
    assert r.result == "fail" and r.evidence == "ref=Z"


def test_s12_text_phrase(registry, cat):
    r = signals(third_party(text="Użyj kodu: mój kod polecający to OLA10."), registry, cat)["S1.2"]
    assert r.result == "fail" and r.evidence == "kod polecający"


def test_s12_no_referral(mock, registry, cat):
    assert signals(mock(KASIA), registry, cat)["S1.2"].result == "pass"


def test_s12_word_inside_word(registry, cat):
    assert signals(third_party(text="Moje preferencje inwestycyjne."), registry, cat)["S1.2"].result == "pass"


def test_s12_malformed_href(registry, cat):
    assert signals(third_party(text="x", links=[{"href": "http://[::1?ref=1"}]), registry, cat)["S1.2"].result == "pass"


# ---- S1.3 --------------------------------------------------------------------------------------


def test_s13_hashtag(mock, registry, cat):
    r = signals(mock(KASIA), registry, cat)["S1.3"]
    assert (r.result, r.evidence) == ("fail", "#współpraca")


def test_s13_no_label(mock, registry, cat):
    assert signals(mock(JAN), registry, cat)["S1.3"].result == "pass"


def test_s13_negated(registry, cat):
    r = signals(third_party(text="To nie jest współpraca reklamowa, kupiłem sam."), registry, cat)["S1.3"]
    assert r.result == "pass"


def test_s13_negated_hashtag_still_counts(registry, cat):
    r = signals(third_party(text="To nie #reklama."), registry, cat)["S1.3"]
    assert (r.result, r.evidence) == ("fail", "#reklama")


def test_s13_sponsored_rel(registry, cat):
    href = "https://alfa-inwestycje.example.com/"
    d = third_party(text="Fajna aplikacja.", links=[{"href": href, "rel": "nofollow sponsored"}])
    r = signals(d, registry, cat)["S1.3"]
    assert (r.result, r.evidence) == ("fail", href) and "sponsored" in r.explanation


def test_s13_label_inside_word(registry, cat):
    assert signals(third_party(text="Mój partnerski program."), registry, cat)["S1.3"].result == "pass"


def test_s13_present_label_raises_absent_does_not_lower(registry, cat):
    plain = third_party(text="Konto w Alfa Inwestycje DM jest wygodne.")
    labeled = third_party(text="Konto w Alfa Inwestycje DM jest wygodne. #współpraca")
    s_plain, s_labeled = finding(plain, registry, cat), finding(labeled, registry, cat)
    assert next(r for r in s_plain.rules if r.rule_id == "S1.3").result == "pass"
    without = [r for r in s_plain.rules if r.rule_id != "S1.3"]
    from investwatch_analytics.rules.scoring import sigmoid_score

    assert s_plain.score == sigmoid_score(without, cat)
    assert s_labeled.score > s_plain.score


# ---- S1.4 --------------------------------------------------------------------------------------


def test_s14_link_in_bio(mock, registry, cat):
    r = signals(mock(JAN), registry, cat)["S1.4"]
    assert r.result == "fail" and r.evidence.startswith("link w bio")


def test_s14_past_tense(mock, registry, cat):
    assert signals(mock(KASIA), registry, cat)["S1.4"].result == "pass"


def test_s14_asks_llm_only_on_pass(cat):
    rule = engine._RULES["S1.4"](cat.get("S1.4"))
    mk = lambda res: engine.Rule(cat.get("S1.4")).result(res, None, "x")  # noqa: E731
    assert rule.ask_llm(None, mk("pass")) is True and rule.ask_llm(None, mk("fail")) is False


# ---- S1.6 --------------------------------------------------------------------------------------


def test_s16_handle(mock, registry, cat):
    r = signals(mock(JAN), registry, cat)["S1.6"]
    assert (r.result, r.evidence) == ("fail", "@inwestor_jan") and "autor" in r.explanation.lower()


def test_s16_name_without_handle(registry, cat):
    r = signals(third_party(text="Alfa Inwestycje", author={"name": "Ola K."}), registry, cat)["S1.6"]
    assert (r.result, r.evidence) == ("fail", "Ola K.")


def test_s16_web_page_host(registry, cat):
    d = third_party(platform="web", url="https://www.blog-ola.example.com/wpis", author=None, text="Alfa Inwestycje")
    r = signals(d, registry, cat)["S1.6"]
    assert (r.result, r.evidence) == ("fail", "blog-ola.example.com")


def test_s16_social_without_author(registry, cat):
    r = signals(third_party(text="Polskie konto w Alfa Inwestycje.", author=None), registry, cat)["S1.6"]
    assert r.result == "not_applicable"


def test_s16_firm_itself_passes(registry, cat):
    r = signals(third_party(text="Alfa Inwestycje", author={"handle": "@alfainwestycje"}), registry, cat)["S1.6"]
    assert r.result == "pass"


# ---- S1.7 --------------------------------------------------------------------------------------


def test_s17_zloty(mock, registry, cat):
    r = signals(mock(JAN), registry, cat)["S1.7"]
    assert r.result == "fail" and "zł" in r.evidence


def test_s17_phone(registry, cat):
    r = signals(third_party(text="Call EuroTrade now: +48 600 100 200"), registry, cat)["S1.7"]
    assert r.result == "fail" and r.evidence.startswith("+48")


def test_s17_pl_host(registry, cat):
    d = third_party(platform="web", url="https://forum.inwestorzy.pl/t/1", author=None, text="EuroTrade is great")
    r = signals(d, registry, cat)["S1.7"]
    assert (r.result, r.evidence) == ("fail", "forum.inwestorzy.pl")


def test_s17_polish_language_only(mock, registry, cat):
    r = signals(mock(KASIA), registry, cat)["S1.7"]
    assert (r.result, r.evidence) == ("fail", None) and "polski" in r.explanation


def test_s17_english_abroad(registry, cat):
    d = third_party(platform="web", url="https://blog.example.com/x", author=None,
                    text="EuroTrade Markets is a great broker for international traders.")
    assert signals(d, registry, cat)["S1.7"].result == "pass"


# ---- score -------------------------------------------------------------------------------------


def test_affiliate_post_score(mock, registry, cat):
    assert finding(mock(JAN), registry, cat).score >= 0.6


def test_labeled_cooperation_score(mock, registry, cat):
    assert finding(mock(KASIA), registry, cat).score >= 0.6


def test_bare_mention_score(registry, cat):
    d = third_party(text="Słyszałem, że Alfa Inwestycje ma nową aplikację mobilną.")
    assert finding(d, registry, cat).score < 0.6


# ---- finding -----------------------------------------------------------------------------------


def test_finfluencer_finding(mock, registry, cat, finding_validator):
    f = finding(mock(JAN), registry, cat)
    assert f.module == "M1" and f.firm.registry_id == EURO and f.firm.authorized is True
    assert ("@inwestor_jan" in f.title or "Jan Inwestor" in f.title) and "EuroTrade" in f.title
    assert "brak oznaczenia współpracy" in f.summary.lower()
    assert f.advertiser.handle == "@inwestor_jan" and f.model.llm is None and f.status == "new"
    assert f.url == mock(JAN).url and f.platform == "instagram" and len(f.content_excerpt) <= 500
    assert "regułowy" in f.summary
    finding_validator.validate(f.to_contract())


def test_labeled_finding_summary(mock, registry, cat):
    f = finding(mock(KASIA), registry, cat)
    assert "#współpraca" in f.summary


def test_metadata_quotes_survive_the_safety_net(mock, registry, cat):
    """The quotes from the handle and the link stay `fail`; none is demoted by the engine's safety net."""
    for doc_id in (JAN, KASIA):
        for r in finding(mock(doc_id), registry, cat).rules:
            assert "Nie udało się potwierdzić cytatu" not in (r.explanation or ""), r.rule_id
    rules = {r.rule_id: r for r in finding(mock(JAN), registry, cat).rules}
    assert rules["S1.2"].result == rules["S1.6"].result == "fail"


@pytest.mark.parametrize("text, quote", [("Bonus 500 złotych na start z Alfa Inwestycje.", "500 złotych"),
                                         ("Alfa Inwestycje: depozyt od 2 tys. zł.", "2 tys. zł"),
                                         ("Alfa Inwestycje, minimum 1000 zl", "1000 zl")])
def test_s17_zloty_forms(registry, cat, text, quote):
    r = signals(third_party(text=text), registry, cat)["S1.7"]
    assert (r.result, r.evidence) == ("fail", quote)


def test_english_ad_of_polish_brokerage_house(registry, cat):
    from investwatch_analytics.rules.scoring import sigmoid_score

    d = third_party(platform="web", url="https://blog.example.com/x", author=None,
                    text="Alfa Inwestycje is a great broker, open an account today.")
    f = finding(d, registry, cat)
    s17 = next(r for r in f.rules if r.rule_id == "S1.7")
    assert f.firm.registry_type == "brokerage_house" and s17.result == "pass"
    assert f.score == sigmoid_score([r for r in f.rules if r.rule_id != "S1.7"], cat)


@pytest.mark.parametrize("href", ["https://x.example.com/?q=1&xref=2", "https://x.example.com/a&ref=1"])
def test_s12_key_must_be_a_whole_query_key(registry, cat, href):
    assert signals(third_party(text="Zobacz.", links=[{"href": href}]), registry, cat)["S1.2"].result == "pass"


def test_s14_quotes_first_phrase(registry, cat):
    r = signals(third_party(text="Kliknij tutaj, a potem załóż konto w Alfa Inwestycje."), registry, cat)["S1.4"]
    assert r.evidence == "Kliknij"


def test_long_post_excerpt_is_cut(registry, cat):
    f = finding(third_party(text="Alfa Inwestycje DM. " + "Słowo " * 400), registry, cat)
    assert len(f.content_excerpt) == 500


# ---- review of #35, items 3 and 4 -------------------------------------------------------------------


def test_bare_partner_is_not_a_label(registry, cat):
    d = third_party(text="Nasz partner biznesowy omawia spotkanie z Alfa Inwestycje DM.")
    f = finding(d, registry, cat)
    assert {r.rule_id: r.result for r in f.rules}["S1.3"] == "pass" and f.score < 0.6


@pytest.mark.parametrize("label", ["#partner", "partner reklamowy"])
def test_partner_as_an_ad_label(registry, cat, label):
    r = signals(third_party(text=f"Konto w Alfa Inwestycje DM ({label})."), registry, cat)["S1.3"]
    assert (r.result, r.evidence) == ("fail", label)


def test_social_post_without_author_has_no_advertiser_name(registry, cat):
    f = finding(third_party(text="Polecam Alfa Inwestycje DM, konto otworzyłem w minutę.", author=None), registry, cat)
    assert f.advertiser.name is None and f.advertiser.website is None
    assert f.title.startswith("Nieznany autor")


# ---- review of #35, items 7 and 10 ------------------------------------------------------------------


def test_plain_mention_title_says_wspomina(registry, cat):
    f = finding(third_party(text="Słyszałem, że Alfa Inwestycje ma nową aplikację mobilną."), registry, cat)
    assert "wspomina" in f.title and "reklamuje" not in f.title


def test_ad_signal_title_says_reklamuje(mock, registry, cat):
    assert "reklamuje" in finding(mock(JAN), registry, cat).title


def test_m1_excerpt_around_the_evidence(registry, cat):
    text = "Długi wstęp o pogodzie i wakacjach. " * 60 + "Na koniec: konto w Alfa Inwestycje DM jest świetne."
    f = finding(third_party(text=text), registry, cat)
    assert len(f.content_excerpt) <= 500 and "Alfa Inwestycje DM" in f.content_excerpt


def test_m1_excerpt_without_text_evidence_is_the_start(registry, cat):
    href = "https://eurotrade-markets.example.com/pl/register?ref=X"
    f = finding(third_party(text="Polecam, link niżej.", links=[{"href": href}]), registry, cat)
    assert f.content_excerpt == "Polecam, link niżej."


def test_m1_excerpt_starts_at_the_earliest_evidence(registry, cat):
    text = "Konto w Alfa Inwestycje DM. " + "Opowieść o wakacjach i pogodzie nad morzem. " * 60 + "Link w bio!"
    f = finding(third_party(text=text), registry, cat)
    assert f.content_excerpt.startswith("Konto w Alfa Inwestycje DM")


def test_m1_texts_name_the_loaded_registry(mock, registry, cat):
    f = finding(mock(JAN), registry, cat)
    assert "rejestru KNF" not in f.summary and "z załadowanego rejestru firm (dane demonstracyjne)" in f.summary
    assert all("rejestru KNF" not in (r.explanation or "") for r in f.rules)
