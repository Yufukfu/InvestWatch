from __future__ import annotations

import re
from pathlib import Path

import pytest

from conftest import make_doc
from investwatch_analytics.models import RULE_ID_PATTERN, ScrapedDocument
from investwatch_analytics.preprocessing import preprocess
from investwatch_analytics.registry import Registry
from investwatch_analytics.rules.engine import Catalogue, CatalogueError, Context, run_rules

SEED = Path(__file__).resolve().parents[1] / "registry" / "seed.csv"


@pytest.fixture(scope="module")
def registry() -> Registry:
    return Registry.from_csv(SEED)


@pytest.fixture(scope="module")
def catalogue() -> Catalogue:
    return Catalogue.load()


def ctx_for(text: str, registry: Registry, url: str = "https://x.example.org/") -> Context:
    doc = ScrapedDocument.model_validate(make_doc(text=text, url=url))
    return Context(doc=doc, pre=preprocess(text), firm_match=registry.match(text, url), registry=registry)


def results(text, registry, catalogue, **kw) -> dict:
    return {r.rule_id: r for r in run_rules(catalogue, ctx_for(text, registry, **kw))}


# ---- catalogue ---------------------------------------------------------------------------------


def test_catalogue_is_complete(catalogue):
    ids = [s.id for s in catalogue.specs]
    assert len(ids) == 19 and len(set(ids)) == 19
    assert all(re.match(RULE_ID_PATTERN, i) for i in ids)
    assert [s.id for s in catalogue.implemented] == ["R1", "R2", "R3"]


def _write(tmp_path, body: str) -> Path:
    p = tmp_path / "rules.yaml"
    p.write_text(body, encoding="utf-8")
    return p


def test_unknown_severity_rejected(tmp_path):
    p = _write(tmp_path, "rules:\n  - {id: R1, name: x, severity: critical, legal_basis: null, implemented: false}\n")
    with pytest.raises(CatalogueError, match="R1"):
        Catalogue.load(p)


def test_duplicate_id_rejected(tmp_path):
    body = "rules:\n" + "  - {id: R2, name: x, severity: low, legal_basis: null, implemented: false}\n" * 2
    with pytest.raises(CatalogueError, match="R2"):
        Catalogue.load(_write(tmp_path, body))


def test_bad_rule_id_rejected(tmp_path):
    p = _write(tmp_path, "rules:\n  - {id: R19, name: x, severity: low, legal_basis: null, implemented: false}\n")
    with pytest.raises(CatalogueError, match="R19"):
        Catalogue.load(p)


def test_implemented_rule_without_code_rejected(tmp_path):
    p = _write(tmp_path, "rules:\n  - {id: R9, name: x, severity: low, legal_basis: null, implemented: true}\n")
    with pytest.raises(CatalogueError, match="R9"):
        Catalogue.load(p)


def test_only_implemented_rules_run(tmp_path, registry):
    body = (
        "rules:\n"
        "  - {id: R4, name: x, severity: low, legal_basis: null, implemented: false}\n"
        "  - {id: R2, name: Oznaczenie reklamy, severity: medium, legal_basis: null, implemented: true}\n"
    )
    cat = Catalogue.load(_write(tmp_path, body))
    assert [s.id for s in cat.implemented] == ["R2"]
    assert [r.rule_id for r in run_rules(cat, ctx_for("Tekst.", registry))] == ["R2"]


def test_results_carry_catalogue_metadata(registry, catalogue):
    r = results("Reklama. Alfa Inwestycje.", registry, catalogue)
    for rule_id in ("R1", "R2", "R3"):
        spec = catalogue.get(rule_id)
        assert (r[rule_id].name, r[rule_id].severity, r[rule_id].legal_basis) == (spec.name, spec.severity, spec.legal_basis)
        assert r[rule_id].method == "rule"
        assert r[rule_id].explanation


def test_evidence_is_exact_quote_on_mocks(mock_documents, registry, catalogue):
    for raw in mock_documents:
        doc = ScrapedDocument.model_validate(raw)
        ctx = Context(doc=doc, pre=preprocess(doc.text), firm_match=registry.match(doc.text, doc.url), registry=registry)
        for res in run_rules(catalogue, ctx):
            assert res.evidence is None or res.evidence in doc.text, (doc.id, res.rule_id)


def test_non_substring_evidence_downgraded_to_uncertain(registry, catalogue, monkeypatch):
    from investwatch_analytics.rules import m2

    monkeypatch.setattr(m2.R2AdLabel, "evaluate", lambda self, ctx: self.result("pass", "Reklama wymyślona", "x"))
    r = results("Brak oznaczenia.", registry, catalogue)["R2"]
    assert r.result == "uncertain" and r.evidence is None


# ---- R1 ----------------------------------------------------------------------------------------


def test_r1_name_present(registry, catalogue):
    r = results("Konto Premium Alfa Inwestycje. Zarabiaj!", registry, catalogue)["R1"]
    assert r.result == "pass" and r.evidence == "Alfa Inwestycje"


def test_r1_domain_only_fails(registry, catalogue):
    r = results("Otwórz konto już dziś.", registry, catalogue, url="https://alfa-inwestycje.example.com/x")["R1"]
    assert r.result == "fail" and r.evidence is None


def test_r1_no_firm_fails(registry, catalogue):
    assert results("Beta Kapitał zaprasza.", registry, catalogue)["R1"].result == "fail"


# ---- R2 ----------------------------------------------------------------------------------------


def test_r2_labeled(registry, catalogue):
    r = results("Reklama. Bank Przykładowy S.A. – Biuro Maklerskie.", registry, catalogue)["R2"]
    assert r.result == "pass" and r.evidence == "Reklama"


def test_r2_hashtag_label(registry, catalogue):
    r = results("Super konto! #reklama #inwestycje", registry, catalogue)["R2"]
    assert r.result == "pass" and r.evidence == "#reklama"


def test_r2_unlabeled(registry, catalogue):
    r = results("Konto Premium Alfa Inwestycje.", registry, catalogue)["R2"]
    assert r.result == "fail" and r.evidence is None


def test_r2_label_inside_word(registry, catalogue):
    assert results("Złóż reklamację w oddziale.", registry, catalogue)["R2"].result == "fail"
    assert results("To antyreklama inwestowania.", registry, catalogue)["R2"].result == "fail"


def test_r2_quotes_first_label_in_text(registry, catalogue):
    r = results("Reklama. Materiał marketingowy firmy.", registry, catalogue)["R2"]
    assert r.evidence == "Reklama"


# ---- R3 ----------------------------------------------------------------------------------------


def test_r3_no_return_claim(registry, catalogue):
    assert results("Otwórz IKE i inwestuj długoterminowo.", registry, catalogue)["R3"].result == "not_applicable"


def test_r3_warning_next_to_claim(registry, catalogue):
    text = "Zyskaj nawet 8% rocznie. Inwestowanie wiąże się z ryzykiem utraty kapitału."
    r = results(text, registry, catalogue)["R3"]
    assert r.result == "pass" and r.evidence == "Inwestowanie wiąże się z ryzykiem utraty kapitału."


def test_r3_warning_at_window_edge_passes(registry, catalogue):
    text = "Zysk 8% rocznie. Zdanie dwa. Zdanie trzy. Ryzyko utraty kapitału."
    assert results(text, registry, catalogue)["R3"].result == "fail"
    text = "Zysk 8% rocznie. Zdanie dwa. Ryzyko utraty kapitału."
    assert results(text, registry, catalogue)["R3"].result == "pass"


def test_r3_warning_before_claim_counts(registry, catalogue):
    text = "Ryzyko utraty kapitału. Zdanie dwa. Zarabiaj 8% rocznie."
    assert results(text, registry, catalogue)["R3"].result == "pass"


def test_r3_footnote_warning_fails(registry, catalogue):
    text = (
        "Konto Premium Alfa Inwestycje. Zarabiaj nawet do 18% rocznie na portfelu ETF! "
        "Dołącz do 50 000 zadowolonych inwestorów. Działamy pod nadzorem KNF – Twoje środki są bezpieczne. "
        "Otwórz konto w 5 minut. *Inwestowanie wiąże się z ryzykiem utraty części lub całości kapitału."
    )
    r = results(text, registry, catalogue)["R3"]
    assert r.result == "fail" and r.evidence == "Zarabiaj nawet do 18% rocznie na portfelu ETF!"


def test_r3_adjacent_footnote_still_fails(registry, catalogue):
    assert results("Zarabiaj 18% rocznie! *Ryzyko utraty kapitału.", registry, catalogue)["R3"].result == "fail"


def test_r3_no_warning_at_all(registry, catalogue):
    r = results("Zarabiaj 18% rocznie! Otwórz konto.", registry, catalogue)["R3"]
    assert r.result == "fail" and r.evidence == "Zarabiaj 18% rocznie!"


def test_r3_every_claim_must_be_covered(registry, catalogue):
    text = "Zysk 8% rocznie. Ryzyko utraty kapitału. Zdanie. Zdanie. Zdanie. Zarobisz 20% w rok."
    r = results(text, registry, catalogue)["R3"]
    assert r.result == "fail" and r.evidence == "Zarobisz 20% w rok."


def test_r3_no_risk_is_not_a_warning(registry, catalogue):
    assert results("Zarabiaj 12% bez ryzyka!", registry, catalogue)["R3"].result == "fail"


def test_r3_zero_commission_is_not_a_return_claim(registry, catalogue):
    assert results("Handluj akcjami. 0% prowizji do końca roku.", registry, catalogue)["R3"].result == "not_applicable"


def test_r3_quotes_nearest_warning(registry, catalogue):
    text = "Zysk 8% rocznie. Ryzyko straty. Zdanie. Zdanie. Zdanie. Ryzyko utraty."
    assert results(text, registry, catalogue)["R3"].evidence == "Ryzyko straty."


def test_r3_return_verb_without_percent_is_a_claim(registry, catalogue):
    assert results("Zarabiaj codziennie z nami! Otwórz konto.", registry, catalogue)["R3"].result == "fail"


def test_r3_risk_word_alone_is_a_warning(registry, catalogue):
    text = "Zysk 8% rocznie. Risk warning: CFDs are complex instruments."
    assert results(text, registry, catalogue)["R3"].result == "pass"


def test_r3_english_warning_counts(registry, catalogue):
    text = "Nasi klienci zarobili średnio 34% w 2025 roku. Risk warning: you may lose money."
    assert results(text, registry, catalogue)["R3"].result == "pass"
