"""M2 stage-3 rules (analytics-m2-p1-rules): R16, R15, R12a, R12b, R11, rules-only.

Kept apart from `test_rules_m2_p0.py` so a parallel `analytics-llm-p0` group does not collide here. Mock
scenarios read `contracts/mocks/documents.json` (never edited) and skip without `CONTRACTS_DIR`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from conftest import make_doc
from investwatch_analytics.models import ScrapedDocument
from investwatch_analytics.preprocessing import preprocess
from investwatch_analytics.registry import Registry
from investwatch_analytics.rules.engine import DEFAULT_CATALOGUE, Catalogue, CatalogueError, Context, run_rules

SEED = Path(__file__).resolve().parents[1] / "registry" / "seed.csv"
EUROTRADE_ID, BANK_OK_ID, ALFA_ID = "c99e2a35", "5030107e", "a3c88321"


@pytest.fixture(scope="module")
def registry() -> Registry:
    return Registry.from_csv(SEED)


@pytest.fixture(scope="module")
def catalogue() -> Catalogue:
    return Catalogue.load()


def run(text: str, registry: Registry, catalogue: Catalogue, **doc_fields) -> dict:
    doc = ScrapedDocument.model_validate(make_doc(text=text, **doc_fields))
    ctx = Context(doc=doc, pre=preprocess(text), firm_match=registry.match(text, doc.url), registry=registry)
    return {r.rule_id: r for r in run_rules(catalogue, ctx)}


def run_mock(mock_documents: list[dict], prefix: str, registry: Registry, catalogue: Catalogue) -> dict:
    raw = next(d for d in mock_documents if d["id"].startswith(prefix))
    doc = ScrapedDocument.model_validate(raw)
    ctx = Context(doc=doc, pre=preprocess(doc.text), firm_match=registry.match(doc.text, doc.url), registry=registry)
    return {r.rule_id: r for r in run_rules(catalogue, ctx)}


def load_with(tmp_path, rule_id: str, params: dict) -> Catalogue:
    data = yaml.safe_load(DEFAULT_CATALOGUE.read_text(encoding="utf-8"))
    entry = next(e for e in data["rules"] if e["id"] == rule_id)
    entry["params"] = {**(entry.get("params") or {}), **params}
    path = tmp_path / "rules.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return Catalogue.load(path)


# ---- R16 tax information ------------------------------------------------------------------------

R16_DISCLAIMER = "Traktowanie podatkowe zależy od indywidualnej sytuacji klienta i może ulec zmianie."


def test_r16_catalogue_entry(catalogue):
    spec = catalogue.get("R16")
    assert spec.implemented
    assert spec.legal_basis == "art. 44 ust. 7 rozp. del. 2017/565"
    assert spec.llm is None  # rules-only


def test_r16_bank_ok_full_disclaimer_passes(mock_documents, registry, catalogue):
    r = run_mock(mock_documents, BANK_OK_ID, registry, catalogue)["R16"]
    assert r.result == "pass"
    assert r.evidence == R16_DISCLAIMER


def test_r16_tax_benefit_without_disclaimer_fails(registry, catalogue):
    text = "Inwestuj bez podatku Belki w IKZE!"
    r = run(text, registry, catalogue)["R16"]
    assert r.result == "fail"
    assert r.evidence == text
    assert "indywidualnej sytuacji" in r.explanation and "zmian" in r.explanation


def test_r16_only_individual_part_fails_naming_change(registry, catalogue):
    partial = "Korzyść podatkowa zależy od indywidualnej sytuacji klienta."
    r = run(f"Otwórz IKZE i odliczaj wpłaty od podatku. {partial}", registry, catalogue)["R16"]
    assert r.result == "fail"
    assert r.evidence == partial
    assert "zmian" in r.explanation
    assert "indywidualnej" not in r.explanation


def test_r16_only_change_part_fails_naming_individual(registry, catalogue):
    partial = "Przepisy podatkowe mogą ulec zmianie."
    r = run(f"Otwórz IKE i inwestuj bez podatku Belki. {partial}", registry, catalogue)["R16"]
    assert r.result == "fail"
    assert r.evidence == partial
    assert "indywidualnej sytuacji" in r.explanation
    assert "zmian" not in r.explanation


def test_r16_unrelated_change_sentence_does_not_count(registry, catalogue):
    text = "Otwórz IKE. Korzyść podatkowa zależy od indywidualnej sytuacji klienta. Oferta może ulec zmianie."
    r = run(text, registry, catalogue)["R16"]
    assert r.result == "fail"
    assert "zmian" in r.explanation


def test_r16_change_part_in_a_separate_tax_sentence_counts(registry, catalogue):
    individual = "Korzyść zależy od indywidualnej sytuacji klienta."
    text = f"Otwórz IKE i inwestuj bez podatku Belki. {individual} Przepisy podatkowe mogą się zmienić."
    r = run(text, registry, catalogue)["R16"]
    assert r.result == "pass"
    assert r.evidence == individual


@pytest.mark.parametrize(
    "text",
    ["Cena zawiera podatek VAT.", "Abonament 99 zł plus podatek od towarów i usług.", R16_DISCLAIMER, "", "Bez kropki"],
    ids=["vat", "vat-long-form", "lone-disclaimer", "empty", "unsegmentable"],
)
def test_r16_not_applicable(text, registry, catalogue):
    r = run(text, registry, catalogue)["R16"]
    assert r.result == "not_applicable"
    assert r.evidence is None


def test_r16_vat_sentence_with_a_real_tax_reference_still_applies(registry, catalogue):
    r = run("Cena zawiera VAT, a zyski w IKE są zwolnione z podatku Belki.", registry, catalogue)["R16"]
    assert r.result == "fail"


def test_r16_eurotrade_not_applicable(mock_documents, registry, catalogue):
    r = run_mock(mock_documents, EUROTRADE_ID, registry, catalogue)["R16"]
    assert r.result == "not_applicable"
    assert r.evidence is None


@pytest.mark.parametrize(
    "text", ["Kurs akcji jest podatny na wahania rynkowe.", "Fundusz jest podatny na zmiany kursów walut.",
             "Przepisy podatkowe mogą ulec zmianie.", "Korzyść podatkowa zależy od indywidualnej sytuacji klienta.",
             "Korzyść zależy od indywidualnej sytuacji podatnika."],
    ids=["podatny", "podatny-currency", "lone-change-part", "lone-individual-part", "taxpayer-in-the-part"],
)
def test_r16_no_tax_reference_not_applicable(text, registry, catalogue):
    assert run(text, registry, catalogue)["R16"].result == "not_applicable"


@pytest.mark.parametrize(
    ("text", "missing"),
    [("Ulga IKZE pozwala odliczyć wpłaty od podatku, a jej wysokość zależy od indywidualnej sytuacji podatnika.", "zmian"),
     ("W IKE nie płacisz podatku Belki, choć przepisy mogą ulec zmianie.", "indywidualnej")],
    ids=["benefit-with-individual-part", "benefit-with-change-part"],
)
def test_r16_tax_claim_inside_a_partial_disclaimer_still_applies(text, missing, registry, catalogue):
    r = run(text, registry, catalogue)["R16"]
    assert r.result == "fail"
    assert r.evidence == text
    assert missing in r.explanation


def test_r16_unknown_param_fails_at_load(tmp_path):
    with pytest.raises(CatalogueError, match=r"R16 has unknown param\(s\) tax_patern"):
        load_with(tmp_path, "R16", {"tax_patern": ["podat"]})


def test_r11_non_list_patterns_fail_at_load(tmp_path):
    with pytest.raises(CatalogueError, match=r"R11 comparison_patterns must be a list"):
        load_with(tmp_path, "R11", {"comparison_patterns": "niż"})

