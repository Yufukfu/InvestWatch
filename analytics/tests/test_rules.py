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
    assert [s.id for s in catalogue.implemented] == ["R1", "R2", "R3", "R4", "R5", "R6", "R7", "R11", "R12a", "R12b", "R14", "R15", "R16", "R17", "R18"]


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


@pytest.mark.parametrize(
    "entry",
    [
        "  - {id: R3, name: x, severity: high, legal_basis: null, implemented: true, params: {window: two}}\n",
        "  - {id: R3, name: x, severity: high, legal_basis: null, implemented: true, params: {claim_patterns: ['(']}}\n",
        "  - R3\n",
    ],
)
def test_malformed_params_fail_at_load(tmp_path, entry):
    with pytest.raises(CatalogueError, match="R3"):
        Catalogue.load(_write(tmp_path, "rules:\n" + entry))


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


@pytest.mark.parametrize(
    "text",
    [
        "Gwarantowany zysk 10% miesięcznie bez żadnego ryzyka!",
        "Zarabiaj 10% rocznie. Brak ryzyka, pełna gwarancja.",
        "Zarabiaj 10% rocznie. Nie ponosisz żadnego ryzyka.",
        "Zarabiaj 10% rocznie. Ryzyko? Minimalne.",
        "Zarabiaj 10% rocznie przy minimalnym ryzyku.",
        "Reklama. Zarabiaj 18% rocznie i nigdy nie stracisz.",
        "Zarabiaj 18% rocznie bez straty kapitału.",
        "Zarabiaj 18% rocznie bez ryzyka utraty kapitału.",
        "Zarabiaj 18% rocznie bez żadnej utraty środków.",
    ],
)
def test_r3_risk_denial_is_not_a_warning(text, registry, catalogue):
    assert results(text, registry, catalogue)["R3"].result == "fail"


@pytest.mark.parametrize(
    "text",
    [
        "Zarabiaj 18% rocznie! * Inwestowanie wiąże się z ryzykiem utraty kapitału.",
        "Zarabiaj 18% rocznie! (*) Inwestowanie wiąże się z ryzykiem utraty kapitału.",
    ],
)
def test_r3_spaced_footnote_markers_are_footnotes(text, registry, catalogue):
    r = results(text, registry, catalogue)["R3"]
    assert r.result == "fail" and r.evidence == "Zarabiaj 18% rocznie!"


def test_r3_income_forms(registry, catalogue):
    assert results("Gwarantowany dochód 1000 zł miesięcznie.", registry, catalogue)["R3"].result == "fail"
    assert results("Stały przychód co miesiąc.", registry, catalogue)["R3"].result == "fail"
    assert results("Do sprawy dochodzi nowa oferta.", registry, catalogue)["R3"].result == "not_applicable"


@pytest.mark.parametrize("text", ["Prowizja 0% na akcje z GPW.", "Konto 100% online."])
def test_r3_non_return_percentages(text, registry, catalogue):
    assert results(text, registry, catalogue)["R3"].result == "not_applicable"


def test_r3_loss_verbs_are_warnings(registry, catalogue):
    assert results("Zarabiaj 18% rocznie! Możesz stracić część pieniędzy.", registry, catalogue)["R3"].result == "pass"
    text = "Zarabiaj 18% rocznie! Nasza strategia działa."
    assert results(text, registry, catalogue)["R3"].result == "fail"


@pytest.mark.parametrize(
    "warning",
    [
        "Inwestycje nie są wolne od ryzyka.",
        "Pamiętaj, że nie ma inwestycji bez ryzyka.",
        "No investment is risk-free.",
        "This product is not risk-free.",
    ],
)
def test_r3_double_negative_disclaimer_is_a_warning(warning, registry, catalogue):
    r = results(f"Zarabiaj 8% rocznie. {warning}", registry, catalogue)["R3"]
    assert r.result == "pass" and r.evidence == warning


def test_r3_english_warning_counts(registry, catalogue):
    text = "Nasi klienci zarobili średnio 34% w 2025 roku. Risk warning: you may lose money."
    assert results(text, registry, catalogue)["R3"].result == "pass"


@pytest.mark.parametrize(
    "warning",
    [
        "Nie jest wykluczona utrata kapitału.",
        "Nie można wykluczyć straty części środków.",
        "Nie da się wykluczyć utraty kapitału.",
        "Nie wykluczamy strat.",
        "Nie gwarantujemy braku strat.",
    ],
)
def test_r3_negated_exclusion_of_loss_is_a_warning(warning, registry, catalogue):
    r = results(f"Zarabiaj 8% rocznie. {warning}", registry, catalogue)["R3"]
    assert r.result == "pass" and r.evidence == warning


@pytest.mark.parametrize(
    "text",
    [
        "To nie jest reklama, to edukacja. Zarabiaj z nami.",
        "Nie reklama, tylko rzetelna informacja.",
        "This is not an advertisement.",
        "To nie jest żadna reklama.",
    ],
)
def test_r2_negated_label_does_not_count(text, registry, catalogue):
    r = results(text, registry, catalogue)["R2"]
    assert r.result == "fail" and r.evidence is None


def test_r2_negated_and_real_label(registry, catalogue):
    r = results("To nie jest reklama, to edukacja. Treść. Reklama.", registry, catalogue)["R2"]
    assert r.result == "pass" and r.evidence == "Reklama"


MIDDLE = "Jeden. Dwa. Materiał reklamowy. Cztery. Pięć. Sześć."


def test_r2_label_buried_mid_text_is_uncertain(registry, catalogue):
    r = results(MIDDLE, registry, catalogue)["R2"]
    assert r.result == "uncertain" and r.evidence == "Materiał reklamowy"


@pytest.mark.parametrize(
    "text",
    [
        "Jeden. Materiał reklamowy. Trzy. Cztery. Pięć. Sześć.",  # second sentence
        "Jeden. Dwa. Trzy. Cztery. Materiał reklamowy. Sześć.",  # second to last
        "Jeden. Dwa. Trzy #reklama. Cztery. Pięć. Sześć.",  # hashtag anywhere
    ],
)
def test_r2_prominent_label_passes(text, registry, catalogue):
    assert results(text, registry, catalogue)["R2"].result == "pass"


def test_r2_prominent_label_beats_earlier_buried_one(registry, catalogue):
    text = "Jeden. Dwa. Reklama w środku. Cztery. Pięć. Materiał marketingowy."
    r = results(text, registry, catalogue)["R2"]
    assert r.result == "pass" and r.evidence == "Materiał marketingowy"


@pytest.mark.parametrize(
    "denial",
    [
        "Nasz fundusz nie tylko wyklucza straty, ale daje spokój.",
        "Nie martw się, wykluczamy straty.",
        "Nie martw się wykluczamy straty.",
        "Nie tylko gwarantujemy brak straty, ale i spokój.",
        "Gwarantujemy uniknięcie straty.",
    ],
)
def test_r3_affirmed_exclusion_of_loss_is_not_a_warning(denial, registry, catalogue):
    assert results(f"Zarabiaj 12% rocznie. {denial}", registry, catalogue)["R3"].result == "fail"


@pytest.mark.parametrize(
    "text",
    [
        "Nie czekaj\nReklama\nKonto. A. B. C.",
        "Nie zwlekaj dłużej\n#reklama\nKonto. A. B. C.",
        "Nie zwlekaj, #reklama nie kłamie. A. B. C. D.",
        "Nie czekaj #ad. A. B. C. D.",
    ],
)
def test_r2_negation_does_not_cross_lines_or_negate_hashtags(text, registry, catalogue):
    assert results(text, registry, catalogue)["R2"].result == "pass"


def test_r2_negation_window_does_not_cut_inside_a_word(registry, catalogue):
    # The 40-char look-back starts right after "Inwestowa", so a sliced window would see "nie".
    text = "Inwestowanie " + "a" * 20 + " " + "b" * 14 + " reklama. Zysk."
    assert results(text, registry, catalogue)["R2"].result == "pass"


def _catalogue_with(tmp_path, old: str, new: str) -> Path:
    src = Path(__file__).resolve().parents[1] / "src" / "investwatch_analytics" / "rules" / "m2_rules.yaml"
    text = src.read_text(encoding="utf-8")
    assert old in text
    return _write(tmp_path, text.replace(old, new))


@pytest.mark.parametrize(
    "old, new, key",
    [
        ("negation_before: '(?:", "negation_before: '((?:", "negation_before"),
        ("negation_before: '", "negation_before: ['x']\n      # '", "negation_before"),
        ("prominent_sentences: 2", "prominent_sentences: two", "prominent_sentences"),
        ("prominent_sentences: 2", "prominent_sentences: -1", "prominent_sentences"),
        ("prominent_sentences: 2", "prominent_sentences: true", "prominent_sentences"),
        ('footnote_markers: &footnote_markers ["*", "¹", "²", "³"]', "footnote_markers: &footnote_markers 5", "footnote_markers"),
        ('footnote_markers: &footnote_markers ["*", "¹", "²", "³"]', 'footnote_markers: &footnote_markers ["*", 1]', "footnote_markers"),
        ('footnote_markers: &footnote_markers ["*", "¹", "²", "³"]', 'footnote_markers: &footnote_markers ["*", ""]', "footnote_markers"),
    ],
)
def test_bad_rule_params_fail_at_load(tmp_path, old, new, key):
    with pytest.raises(CatalogueError, match=key):
        Catalogue.load(_catalogue_with(tmp_path, old, new))


def test_catalogue_root_must_be_a_mapping(tmp_path):
    with pytest.raises(CatalogueError, match="mapping"):
        Catalogue.load(_write(tmp_path, "- id: R1\n"))


@pytest.mark.parametrize(
    "text",
    [
        "Zysk 10% rocznie, bez opłat ryzyko utraty kapitału.",
        "Zysk 10% rocznie. Bez opłat, ale ryzyko utraty kapitału istnieje.",
        "Zysk 10% rocznie. Nie pobieramy opłat ryzyko straty ponosisz Ty.",
    ],
)
def test_r3_denial_word_does_not_swallow_a_following_warning(text, registry, catalogue):
    assert results(text, registry, catalogue)["R3"].result == "pass"


@pytest.mark.parametrize(
    "text",
    [
        "To nie tylko reklama – to Twoja szansa.",
        "To nie jest tylko reklama.",
        "Not just an advertisement.",
        "To nie jedynie materiał reklamowy.",
    ],
)
def test_r2_not_only_does_not_negate(text, registry, catalogue):
    assert results(text, registry, catalogue)["R2"].result == "pass"


@pytest.mark.parametrize(
    "denial",
    [
        "Zero ryzyk.",
        "Brak ryzyk.",
        "Bez ryzyk!",
        "I nie ponosisz żadnych ryzyk.",
        "Nie ma ryzyka utraty kapitału.",
        "Nie ma ryzyka straty.",
        "Żadnego ryzyka straty.",
        "Nie ma żadnego ryzyka utraty.",
        "Nie istnieje ryzyko utraty kapitału.",
        "Nie ma ryzyka.",
    ],
)
def test_r3_plural_and_nie_ma_denials_are_not_warnings(denial, registry, catalogue):
    assert results(f"Zarabiaj 12% rocznie. {denial}", registry, catalogue)["R3"].result == "fail"


def test_empty_label_fails_at_load(tmp_path):
    with pytest.raises(CatalogueError, match="labels"):
        Catalogue.load(_catalogue_with(tmp_path, "        - reklama\n", '        - ""\n'))


def test_unknown_param_key_fails_at_load(tmp_path):
    with pytest.raises(CatalogueError, match="windw"):
        Catalogue.load(_catalogue_with(tmp_path, "      window: 2", "      windw: 2"))
