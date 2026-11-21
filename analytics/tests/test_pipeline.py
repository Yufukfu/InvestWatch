from __future__ import annotations

import logging
import uuid
from pathlib import Path

import pytest

from conftest import NOW, make_doc
from investwatch_analytics.config import PIPELINE_VERSION
from investwatch_analytics.models import RuleResult, ScrapedDocument
from investwatch_analytics.modules.m2 import score
from investwatch_analytics.modules.router import route
from investwatch_analytics.pipeline import analyze
from investwatch_analytics.registry import Registry
from investwatch_analytics.rules.engine import Catalogue

SEED = Path(__file__).resolve().parents[1] / "registry" / "seed.csv"
ALFA_DOC = "a3c88321-15bf-56e4-8d59-05a9033308c6"
BANK_DOC = "5030107e-63fe-567c-b076-ccfac4197430"
ALFA_TEXT = (
    "Konto Premium Alfa Inwestycje. Zarabiaj nawet do 18% rocznie na portfelu ETF! "
    "Dołącz do 50 000 zadowolonych inwestorów. Działamy pod nadzorem KNF – Twoje środki są bezpieczne. "
    "Otwórz konto w 5 minut. *Inwestowanie wiąże się z ryzykiem utraty części lub całości kapitału."
)


@pytest.fixture(scope="module")
def registry() -> Registry:
    return Registry.from_csv(SEED)


@pytest.fixture(scope="module")
def catalogue() -> Catalogue:
    return Catalogue.load()


def run(raw: dict, registry, catalogue):
    return analyze(ScrapedDocument.model_validate(raw), registry=registry, catalogue=catalogue, now=NOW)


def rr(result: str, severity: str) -> RuleResult:
    return RuleResult(rule_id="R1", name="x", result=result, severity=severity)


# ---- score -------------------------------------------------------------------------------------


def test_score_formula():
    rules = [rr("fail", "high"), rr("pass", "medium"), rr("not_applicable", "low"), rr("uncertain", "low")]
    assert score(rules) == pytest.approx((3 * 1 + 0 + 0.5 * 1) / (3 + 2 + 1), abs=1e-3)


def test_score_all_pass_is_zero():
    assert score([rr("pass", "high"), rr("not_applicable", "low")]) == 0


def test_score_nothing_applicable_is_zero():
    assert score([rr("not_applicable", "high")]) == 0
    assert score([]) == 0


def test_score_all_fail_is_one():
    assert score([rr("fail", "low"), rr("fail", "high")]) == 1


# ---- routing -----------------------------------------------------------------------------------


MOCK = {"jan": "3c41441c-40ba-5864-b3e0-03f8bc9acebe", "kasia": "182e5a42-1041-5147-99dc-84d73ed34220",
        "edu": "8721cb75-d75c-537f-8981-07a7e2dede3c", "gold": "007bbcee-0737-5c6d-b9b4-ce56fcbfa8e4",
        "vip": "cdbf5306-1bb9-5d3b-b8b8-bc64f2ed8e88", "blog": "72acbb3b-3546-5c9b-9b26-2b29f69ccce9"}
SOCIAL = {"source_kind": "third_party", "platform": "instagram", "url": "https://www.instagram.com/p/R1/"}


def modules_of(findings) -> list[str]:
    return [f.module for f in findings]


def reasons(caplog) -> set[str]:
    return {getattr(r, "reason", None) for r in caplog.records}


def test_route_firm_own_to_m2(registry):
    r = route(ScrapedDocument.model_validate(make_doc(source_kind="firm_own", text="Alfa Inwestycje")), registry)
    assert r.module == "M2" and r.firm_match.firm.name.startswith("Alfa")


def test_firm_own_on_firm_domain(registry, catalogue):
    raw = make_doc(url="https://alfa-inwestycje.example.com/oferta", text="Reklama. Otwórz konto.")
    assert modules_of(run(raw, registry, catalogue)) == ["M2"]


def test_unmatched_own_page_with_advisory_goes_to_m3(registry, catalogue):
    raw = make_doc(text="Beta Kapitał – family office. Rekomendujemy kupno obligacji. Abonament 500 zł miesięcznie.")
    [f] = run(raw, registry, catalogue)
    assert f.module == "M3" and f.firm is None


def test_unmatched_own_page_without_advisory(registry, catalogue, caplog):
    with caplog.at_level(logging.INFO):
        assert run(make_doc(text="Reklama. Beta Kapitał zaprasza na piknik."), registry, catalogue) == []
    assert "no_signals" in reasons(caplog)


def test_firms_own_social_account_goes_to_m2(registry, catalogue):
    raw = make_doc(**SOCIAL, text="Alfa Inwestycje: nowe konto IKE. Otwórz konto.", author={"handle": "@alfainwestycje"})
    [f] = run(raw, registry, catalogue)
    assert f.module == "M2" and f.firm.name.startswith("Alfa") and f.firm.match_confidence == 0.95


def test_firm_account_naming_another_firm_is_still_its_m2(registry, catalogue):
    raw = make_doc(**SOCIAL, text="Bank Przykładowy jest naszym bankiem depozytariuszem.",
                   author={"handle": "@alfainwestycje"})
    [f] = run(raw, registry, catalogue)
    assert f.module == "M2" and f.firm.name.startswith("Alfa")
    assert {r.rule_id: r.result for r in f.rules}["R1"] == "fail"


def test_third_party_post_about_registered_firm(mock_documents, registry, catalogue):
    docs = {d["id"]: d for d in mock_documents}
    assert modules_of(run(docs[MOCK["jan"]], registry, catalogue)) == ["M1"]
    assert modules_of(run(docs[MOCK["kasia"]], registry, catalogue)) == ["M1"]


def test_foreign_firm_ad_not_aimed_at_poland(registry, catalogue, caplog):
    raw = make_doc(source_kind="third_party", platform="web", url="https://blog.example.com/x",
                   text="Atlantic Brokers is a great broker for international traders.")
    with caplog.at_level(logging.INFO):
        assert run(raw, registry, catalogue) == []
    assert "not_targeting_poland" in reasons(caplog)


def test_polish_brokerage_house_advertised_in_english(registry, catalogue):
    raw = make_doc(source_kind="third_party", platform="web", url="https://blog.example.com/x",
                   text="Alfa Inwestycje is a great broker, open an account today.")
    [f] = run(raw, registry, catalogue)
    assert f.module == "M1" and {r.rule_id: r.result for r in f.rules}["S1.7"] == "pass"


def test_unknown_page_of_unregistered_entity(mock_documents, registry, catalogue):
    docs = {d["id"]: d for d in mock_documents}
    assert modules_of(run(docs[MOCK["gold"]], registry, catalogue)) == ["M3"]


def test_unmatched_post_without_advisory(mock_documents, registry, catalogue, caplog):
    docs = {d["id"]: d for d in mock_documents}
    with caplog.at_level(logging.INFO):
        assert run(docs[MOCK["edu"]], registry, catalogue) == []
    assert "no_signals" in reasons(caplog) and "module_not_implemented" not in reasons(caplog)


def test_empty_third_party_text(registry, catalogue, caplog):
    with caplog.at_level(logging.INFO):
        assert run(make_doc(**SOCIAL, text="  "), registry, catalogue) == []
    assert "empty_text" in reasons(caplog)


def test_referral_link_routes_to_m1(registry, catalogue):
    raw = make_doc(**SOCIAL, text="Polecam, link niżej. Bonus 200 zł.",
                   links=[{"href": "https://eurotrade-markets.example.com/pl/register?ref=X"}])
    [f] = run(raw, registry, catalogue)
    assert f.module == "M1" and f.firm.name.startswith("EuroTrade")


def test_malformed_link_routes_to_m3(registry, catalogue):
    raw = make_doc(**SOCIAL, text="Doradztwo inwestycyjne dla każdego. Abonament 99 zł/mies.", links=[{"href": "not a url"}])
    [f] = run(raw, registry, catalogue)
    assert f.module == "M3"


def test_social_domain_in_registry_never_routes_by_page_host(catalogue):
    from investwatch_analytics.modules.router import route
    from investwatch_analytics.registry import Firm

    firm = Firm(id="facc6bd1-c728-5348-90a4-011b0972fea9", name="Alfa Inwestycje", type="brokerage_house",
                country="PL", aliases=(), domains=("instagram.com",), source_url=None)
    doc = ScrapedDocument.model_validate(make_doc(**SOCIAL, text="Doradztwo inwestycyjne, abonament 99 zł/mies."))
    assert route(doc, Registry([firm])).module == "M3"


def test_firm_own_ignores_link_hosts(registry, catalogue):
    raw = make_doc(text="Beta Kapitał zaprasza na piknik.",
                   links=[{"href": "https://alfa-inwestycje.example.com/"}])
    assert run(raw, registry, catalogue) == []


def test_finfluencer_buy_calls_give_m1_and_m3(registry, catalogue):
    raw = make_doc(**SOCIAL, author={"handle": "@trader_ola"},
                   text="Konto mam w EuroTrade Markets. Moja grupa: co tydzień mówię, co kupić z akcji WIG20.")
    findings = run(raw, registry, catalogue)
    assert modules_of(findings) == ["M1", "M3"]
    m1, m3 = findings
    assert m1.firm.name.startswith("EuroTrade") and m3.firm is None and m3.advertiser.handle == "@trader_ola"
    assert m1.id != m3.id


def test_firms_offer_gives_only_m1(registry, catalogue):
    raw = make_doc(**SOCIAL, text="Alfa Inwestycje DM rekomenduje kupno obligacji skarbowych.")
    assert modules_of(run(raw, registry, catalogue)) == ["M1"]


def test_signal_catalogues_can_be_injected(registry, catalogue, tmp_path):
    from investwatch_analytics.pipeline import SignalCatalogues, default_signal_catalogues

    default = default_signal_catalogues()
    assert default is default_signal_catalogues()
    m1 = Catalogue.load(_write_m1(tmp_path), module="M1")
    raw = make_doc(**SOCIAL, text="Polski post: Alfa Inwestycje DM.")
    [f] = analyze(ScrapedDocument.model_validate(raw), registry=registry, catalogue=catalogue, now=NOW,
                  signals=SignalCatalogues(m1=m1, m3=default.m3))
    assert [r.rule_id for r in f.rules] == ["S1.1"]


def _write_m1(tmp_path) -> Path:
    p = tmp_path / "m1.yaml"
    p.write_text("bias: 0\nrules:\n  - {id: S1.1, name: Wzmianka, severity: medium, weight: 1, implemented: true}\n",
                 encoding="utf-8")
    return p


def test_empty_text_yields_nothing(registry, catalogue, caplog):
    with caplog.at_level(logging.INFO):
        assert run(make_doc(text="  \n "), registry, catalogue) == []
    assert any(getattr(r, "reason", None) == "empty_text" for r in caplog.records)


# ---- M2 finding --------------------------------------------------------------------------------


def test_violating_landing_page(registry, catalogue):
    raw = make_doc(text=ALFA_TEXT, url="https://alfa-inwestycje.example.com/konto-premium")
    [f] = run(raw, registry, catalogue)
    by_id = {r.rule_id: r.result for r in f.rules}
    assert by_id == {"R1": "pass", "R2": "fail", "R3": "fail"}
    assert f.module == "M2" and f.score > 0.5 and f.status == "new"
    assert f.firm.name == "Alfa Inwestycje Dom Maklerski S.A." and f.firm.authorized
    assert f.firm.registry_id == "facc6bd1-c728-5348-90a4-011b0972fea9" and f.firm.registry_type == "brokerage_house"
    assert f.url == raw["url"] and f.platform == "web" and f.document_id == raw["id"]
    assert f.model.llm is None and f.model.pipeline_version == PIPELINE_VERSION
    assert f.detected_at == f.updated_at == NOW
    assert uuid.UUID(f.id).version == 4
    assert "Oznaczenie reklamy" in f.title and "Informacja o ryzyku" in f.summary


def test_finding_is_logged_at_info(registry, catalogue, caplog):
    with caplog.at_level(logging.INFO):
        [f] = run(make_doc(text=ALFA_TEXT), registry, catalogue)
    rec = next(r for r in caplog.records if r.getMessage() == "finding built")
    assert rec.finding_module == "M2" and rec.score == f.score


def test_finding_url_is_document_url_not_canonical(registry, catalogue):
    raw = make_doc(text=ALFA_TEXT, url="https://a.example.com/x?ref=1", canonical_url="https://a.example.com/x")
    [f] = run(raw, registry, catalogue)
    assert f.url == "https://a.example.com/x?ref=1"


def test_compliant_material(registry, catalogue):
    text = (
        "Reklama. Bank Przykładowy S.A. – Biuro Maklerskie. Otwórz IKE i inwestuj długoterminowo. "
        "Inwestowanie w instrumenty finansowe wiąże się z ryzykiem utraty części lub całości zainwestowanego kapitału."
    )
    [f] = run(make_doc(text=text), registry, catalogue)
    assert all(r.result != "fail" for r in f.rules)
    assert f.score == 0
    assert "brak naruszeń" in f.title


def test_m2_builder_without_a_firm_match(registry, catalogue):
    from investwatch_analytics.modules import m2
    from investwatch_analytics.preprocessing import preprocess
    from investwatch_analytics.rules.engine import Context

    doc = ScrapedDocument.model_validate(make_doc(text="Reklama. Beta Kapitał zaprasza do inwestowania."))
    ctx = Context(doc=doc, pre=preprocess(doc.text), firm_match=None, registry=registry)
    f = m2.build_finding(ctx, catalogue, now=NOW)
    assert f.firm is None
    assert {r.rule_id: r.result for r in f.rules}["R1"] == "fail"
    assert "Nieznana firma" in f.title


def test_only_implemented_rules_are_listed(registry, catalogue):
    [f] = run(make_doc(text=ALFA_TEXT), registry, catalogue)
    assert [r.rule_id for r in f.rules] == ["R1", "R2", "R3"]


def test_excerpt_is_capped_at_500(registry, catalogue):
    [f] = run(make_doc(text="Reklama. Alfa Inwestycje. " + "Słowo " * 200), registry, catalogue)
    assert len(f.content_excerpt) <= 500


def test_mock_documents_match_spec(mock_documents, registry, catalogue, finding_validator):
    docs = {d["id"]: d for d in mock_documents}
    [alfa] = run(docs[ALFA_DOC], registry, catalogue)
    assert {r.rule_id: r.result for r in alfa.rules} == {"R1": "pass", "R2": "fail", "R3": "fail"} and alfa.score > 0.5
    [bank] = run(docs[BANK_DOC], registry, catalogue)
    assert all(r.result != "fail" for r in bank.rules) and bank.score == 0
    for raw in mock_documents:
        for f in run(raw, registry, catalogue):
            assert [e.message for e in finding_validator.iter_errors(f.to_contract())] == []


def test_summary_lists_only_applicable_rules(registry, catalogue):
    [f] = run(make_doc(text="Reklama. Alfa Inwestycje. Otwórz konto."), registry, catalogue)
    assert {r.rule_id: r.result for r in f.rules}["R3"] == "not_applicable"
    assert "Sprawdzono reguły R1, R2 " in f.summary
    assert "Nie dotyczy: R3 Informacja o ryzyku." in f.summary


def test_summary_without_not_applicable_rules(registry, catalogue):
    [f] = run(make_doc(text=ALFA_TEXT), registry, catalogue)
    assert "Sprawdzono reguły R1, R2, R3 " in f.summary and "Nie dotyczy" not in f.summary


def test_summary_when_no_rule_applies():
    from investwatch_analytics.modules.m2 import _texts

    _, summary = _texts([rr("not_applicable", "high")], None)
    assert "Sprawdzono" not in summary and "Żadna z reguł nie miała zastosowania" in summary
    assert "Nie dotyczy: R1 x." in summary


def test_six_m1_m3_mocks(mock_documents, registry, catalogue, finding_validator):
    """Routing, contract validity and evidence of the six M1/M3 mock documents (read-only test double)."""
    docs = {d["id"]: d for d in mock_documents}
    expected = {"jan": ["M1"], "kasia": ["M1"], "edu": [], "gold": ["M3"], "vip": ["M3"], "blog": ["M3"]}
    for key, modules in expected.items():
        findings = run(docs[MOCK[key]], registry, catalogue)
        assert modules_of(findings) == modules, key
        for f in findings:
            assert [e.message for e in finding_validator.iter_errors(f.to_contract())] == []
            assert all("Nie udało się potwierdzić cytatu" not in (r.explanation or "") for r in f.rules), key


def test_firm_account_naming_itself_after_another_firm(registry, catalogue):
    raw = make_doc(**SOCIAL, text="Bank Przykładowy przechowuje środki klientów Alfa Inwestycje.",
                   author={"handle": "@alfainwestycje"})
    [f] = run(raw, registry, catalogue)
    assert f.firm.name.startswith("Alfa") and f.firm.match_confidence == 0.95
    assert {r.rule_id: r.result for r in f.rules}["R1"] == "pass"


def test_foreign_ad_not_aimed_at_poland_gives_no_m3_either(registry, catalogue, caplog):
    raw = make_doc(source_kind="third_party", platform="web", url="https://blog.example.com/x", author={"handle": "@fx_joe"},
                   text="Atlantic Brokers is my broker and I trade with it every single day of the week. "
                        "Join my private group where I post the trades: co kupić z akcji.")
    with caplog.at_level(logging.INFO):
        assert run(raw, registry, catalogue) == []
    assert "not_targeting_poland" in reasons(caplog)


# ---- review of #35, items 5 and 6 -------------------------------------------------------------------


def test_foreign_branch_advertised_in_english(registry, catalogue):
    raw = make_doc(source_kind="third_party", platform="web", url="https://blog.example.com/x",
                   text="EuroTrade Markets is a great broker for international traders.")
    [f] = run(raw, registry, catalogue)
    assert f.module == "M1" and f.firm.registry_type == "foreign_branch"
    assert {r.rule_id: r.result for r in f.rules}["S1.7"] == "pass"


def test_kacpers_english_advisory_offer(registry, catalogue):
    raw = make_doc(source_kind="unknown", platform="web", url="https://advisors.example.com/",
                   text="We offer investment consulting and wealth advisory for Polish clients. Fee: 2000 PLN per month.")
    [f] = run(raw, registry, catalogue)
    rules = {r.rule_id: r.result for r in f.rules}
    assert f.module == "M3" and rules["S3.2"] == "fail" and rules["S3.5"] == "fail"



# ---- review of #35, item 12: own material of a foreign firm without a Polish branch -----------------


def test_foreign_no_branch_own_account_is_out_of_scope(registry, catalogue, caplog):
    raw = make_doc(**SOCIAL, author={"handle": "@atlanticbrokers"},
                   text="Atlantic Brokers: otwórz konto i zarabiaj 20% rocznie. Rekomendujemy kupno akcji.")
    with caplog.at_level(logging.INFO):
        assert run(raw, registry, catalogue) == []
    assert "out_of_scope_m2_foreign_no_branch" in reasons(caplog)


def test_foreign_no_branch_own_page_is_out_of_scope(registry, catalogue, caplog):
    raw = make_doc(url="https://atlantic-brokers.example.com/pl/oferta", text="Reklama. Atlantic Brokers – konto CFD.")
    with caplog.at_level(logging.INFO):
        assert run(raw, registry, catalogue) == []
    assert "out_of_scope_m2_foreign_no_branch" in reasons(caplog)


def test_third_party_post_about_foreign_no_branch_firm_is_m1(registry, catalogue):
    raw = make_doc(**SOCIAL, author={"handle": "@ola"}, text="Polecam Atlantic Brokers, bonus 200 zł na start.")
    [f] = run(raw, registry, catalogue)
    assert f.module == "M1" and f.firm.registry_type == "foreign_no_branch"


def test_foreign_branch_own_page_stays_m2(registry, catalogue):
    raw = make_doc(url="https://eurotrade-markets.example.com/pl", text="Reklama. EuroTrade Markets – konto.")
    assert modules_of(run(raw, registry, catalogue)) == ["M2"]


def test_foreign_no_branch_own_page_matched_by_name_is_out_of_scope(registry, catalogue, caplog):
    raw = make_doc(url="https://landing.example.com/atlantic", text="Reklama. Atlantic Brokers – konto CFD w 5 minut.")
    with caplog.at_level(logging.INFO):
        assert run(raw, registry, catalogue) == []
    assert "out_of_scope_m2_foreign_no_branch" in reasons(caplog)
