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


def test_route_firm_own_to_m2():
    assert route(ScrapedDocument.model_validate(make_doc(source_kind="firm_own"))) == ["M2"]


@pytest.mark.parametrize("kind", ["third_party", "unknown"])
def test_third_party_is_skipped_with_reason(kind, registry, catalogue, caplog):
    with caplog.at_level(logging.INFO):
        assert run(make_doc(source_kind=kind, text="Polecam Alfa Inwestycje! Zarabiaj 18%."), registry, catalogue) == []
    assert any(getattr(r, "reason", None) == "module_not_implemented" for r in caplog.records)


def test_empty_text_yields_nothing(registry, catalogue, caplog):
    with caplog.at_level(logging.INFO):
        assert run(make_doc(text="  \n "), registry, catalogue) == []
    assert any(getattr(r, "reason", None) == "empty_text" for r in caplog.records)


# ---- M2 finding --------------------------------------------------------------------------------


def test_violating_landing_page(registry, catalogue):
    raw = make_doc(text=ALFA_TEXT, url="https://alfa-inwestycje.example.com/konto-premium")
    [f] = run(raw, registry, catalogue)
    by_id = {r.rule_id: r.result for r in f.rules}
    assert {k: by_id[k] for k in ("R1", "R2", "R3")} == {"R1": "pass", "R2": "fail", "R3": "fail"}
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


def test_unmatched_firm_on_own_page(registry, catalogue):
    [f] = run(make_doc(text="Reklama. Beta Kapitał zaprasza do inwestowania."), registry, catalogue)
    assert f.firm is None
    assert {r.rule_id: r.result for r in f.rules}["R1"] == "fail"
    assert "Nieznana firma" in f.title


def test_only_implemented_rules_are_listed(registry, catalogue):
    [f] = run(make_doc(text=ALFA_TEXT), registry, catalogue)
    assert [r.rule_id for r in f.rules] == [s.id for s in catalogue.implemented]


def test_excerpt_is_capped_at_500(registry, catalogue):
    [f] = run(make_doc(text="Reklama. " + "Słowo " * 200), registry, catalogue)
    assert len(f.content_excerpt) <= 500


def test_mock_documents_match_spec(mock_documents, registry, catalogue, finding_validator):
    docs = {d["id"]: d for d in mock_documents}
    [alfa] = run(docs[ALFA_DOC], registry, catalogue)
    got = {r.rule_id: r.result for r in alfa.rules}
    assert {k: got[k] for k in ("R1", "R2", "R3")} == {"R1": "pass", "R2": "fail", "R3": "fail"} and alfa.score > 0.5
    [bank] = run(docs[BANK_DOC], registry, catalogue)
    assert all(r.result != "fail" for r in bank.rules) and bank.score == 0
    for raw in mock_documents:
        for f in run(raw, registry, catalogue):
            assert [e.message for e in finding_validator.iter_errors(f.to_contract())] == []


def test_summary_lists_only_applicable_rules(registry, catalogue):
    [f] = run(make_doc(text="Reklama. Alfa Inwestycje. Otwórz konto."), registry, catalogue)
    assert {r.rule_id: r.result for r in f.rules}["R3"] == "not_applicable"
    assert "Sprawdzono reguły R1, R2 " in f.summary
    assert "Nie dotyczy: R3 Informacja o ryzyku" in f.summary


def test_summary_without_not_applicable_rules(registry, catalogue):
    [f] = run(make_doc(text=ALFA_TEXT), registry, catalogue)
    assert "Sprawdzono reguły R1, R2, R3" in f.summary
    not_applicable = f.summary.split("Nie dotyczy:", 1)[1] if "Nie dotyczy:" in f.summary else ""
    assert not any(f"{rid} " in not_applicable.split(".")[0] for rid in ("R1", "R2", "R3"))


def test_summary_when_no_rule_applies():
    from investwatch_analytics.modules.m2 import _texts

    _, summary = _texts([rr("not_applicable", "high")], None)
    assert "Sprawdzono" not in summary and "Żadna z reguł nie miała zastosowania" in summary
    assert "Nie dotyczy: R1 x." in summary
