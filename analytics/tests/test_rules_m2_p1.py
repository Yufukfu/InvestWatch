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
             "Korzyść zależy od indywidualnej sytuacji podatnika.",
             "Opodatkowanie zależy od indywidualnej sytuacji klienta.",
             "Kwestie podatkowe zależą od indywidualnej sytuacji klienta.",
             "Zasady opodatkowania zależą od indywidualnej sytuacji klienta i mogą ulec zmianie.",
             "Taxation depends on individual circumstances and may change."],
    ids=["podatny", "podatny-currency", "lone-change-part", "lone-individual-part", "taxpayer-in-the-part",
         "opodatkowanie", "kwestie-podatkowe", "zasady-opodatkowania", "taxation"],  # group 3 review
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


# ---- R15 forecasts ------------------------------------------------------------------------------

FORECAST_WARNING = "Prognozy nie są wiarygodnym wskaźnikiem przyszłych wyników."
FETCHED_2026 = {"fetched_at": "2026-11-21T12:00:00Z"}


def test_r15_catalogue_entry(catalogue):
    spec = catalogue.get("R15")
    assert spec.implemented
    assert spec.legal_basis == "art. 44 ust. 6 rozp. del. 2017/565"


def test_r15_eurotrade_forecast_without_warning_fails(mock_documents, registry, catalogue):
    r = run_mock(mock_documents, EUROTRADE_ID, registry, catalogue)["R15"]
    assert r.result == "fail"
    assert r.evidence == "W przyszłym roku spodziewamy się jeszcze lepszych wyników."
    assert r.method == "rule"


def test_r15_forecast_with_warning_is_reported_as_pass(registry, catalogue):
    forecast = "Prognozujemy stopę zwrotu 6% w 2027 roku."
    r = run(f"{forecast} {FORECAST_WARNING}", registry, catalogue, **FETCHED_2026)["R15"]
    assert r.result == "pass"
    assert r.evidence == forecast
    assert r.explanation.startswith("Wykryto prognozę")
    assert FORECAST_WARNING in r.explanation


def test_r15_weak_marker_with_figure_fails(registry, catalogue):
    text = "Fundusz będzie zarabiał 12% rocznie."
    r = run(text, registry, catalogue)["R15"]
    assert r.result == "fail"
    assert r.evidence == text


def test_r15_weak_marker_without_figure_is_uncertain(registry, catalogue):
    text = "Wyniki będą zależeć od sytuacji rynkowej."
    r = run(text, registry, catalogue)["R15"]
    assert r.result == "uncertain"
    assert r.evidence == text


def test_r15_weak_marker_without_figure_and_warning_passes(registry, catalogue):
    r = run(f"Wyniki będą zależeć od sytuacji rynkowej. {FORECAST_WARNING}", registry, catalogue)["R15"]
    assert r.result == "pass"


def test_r15_past_performance_disclaimer_does_not_cover_a_forecast(registry, catalogue):
    forecast = "Prognozujemy wzrost wyników o 6% w 2027 roku."
    text = f"{forecast} Wyniki historyczne nie są gwarancją przyszłych wyników."
    r = run(text, registry, catalogue, **FETCHED_2026)["R15"]
    assert r.result == "fail"
    assert r.evidence == forecast


def test_r15_alfa_imperative_is_not_a_forecast(mock_documents, registry, catalogue):
    results = run_mock(mock_documents, ALFA_ID, registry, catalogue)
    assert results["R15"].result == "not_applicable"
    assert results["R15"].evidence is None
    assert results["R3"].result == "fail"  # the missing warning next to the return claim stays R3's


@pytest.mark.parametrize(
    "text",
    [FORECAST_WARNING, "Zyskaj 10% i zarabiaj więcej!", "Pomnażaj kapitał – zarabiaj nawet 15% rocznie.",
     "Opłata za zarządzanie będzie wynosić 2%.", "Konto będzie aktywne w 5 minut.", "", "Bez kropki"],
    ids=["lone-warning", "imperatives", "imperative-figure", "fee-percent-with-bedzie", "bedzie-without-results",
         "empty", "unsegmentable"],
)
def test_r15_not_applicable(text, registry, catalogue):
    r = run(text, registry, catalogue)["R15"]
    assert r.result == "not_applicable"
    assert r.evidence is None


@pytest.mark.parametrize(
    "text",
    ["Po odliczeniu opłat fundusz będzie zarabiał 8% rocznie.",
     "Prognozujemy, że po potrąceniu kosztów fundusz wypracuje 6% rocznie."],
    ids=["fee-word-before-weak-forecast", "fee-word-before-strong-forecast"],
)
def test_r15_fee_word_does_not_hide_the_forecast(text, registry, catalogue):
    # The fee-percentage exclude ties the figure to the fee word; it never blanks a return verb (group 3 review).
    r = run(text, registry, catalogue)["R15"]
    assert r.result == "fail"
    assert r.evidence == text


@pytest.mark.parametrize(
    "text",
    ["Opłata za zarządzanie: będzie wynosić 2%.",
     "Podatek od zysków kapitałowych (19%) będzie pobierany automatycznie.",
     "Opłata za zarządzanie w 2027 roku będzie wynosić 2%."],
    ids=["punctuation", "tax-in-brackets", "five-words"],
)
def test_r15_fee_or_tax_percentage_is_not_a_forecast(text, registry, catalogue):
    # Group 4 review: the fee exclude must not depend on whole words between the fee word and the figure.
    assert run(text, registry, catalogue, **FETCHED_2026)["R15"].result == "not_applicable"


def test_r15_noun_zysk_after_a_fee_word_keeps_the_forecast(registry, catalogue):
    # Group 5 review: the fee exclude stops at the return noun `zysk` too (not `zysków`).
    text = "Po odliczeniu opłat zysk funduszu będzie wynosił 8%."
    assert run(text, registry, catalogue, **FETCHED_2026)["R15"].result == "fail"


def test_r15_fee_word_before_a_digit_run_is_fast(registry, catalogue):
    import time

    text = "Fundusz zarobił 8% w 2025 r. Opłata" + "1" * 2000 + " będzie."
    started = time.perf_counter()
    run(text, registry, catalogue)
    assert time.perf_counter() - started < 2.0  # 13 s with `\w*` after the stem


def test_r15_year_after_fetch_year_is_a_strong_marker(registry, catalogue):
    text = "W 2028 roku wyniki funduszu wzrosną."
    assert run(text, registry, catalogue, **FETCHED_2026)["R15"].result == "fail"
    # The same sentence about a past year is not a forecast.
    assert run("W 2025 roku wyniki funduszu wzrosły.", registry, catalogue, **FETCHED_2026)["R15"].result == "not_applicable"


def test_r15_future_tense_verb_with_figure_in_fetch_year_fails(registry, catalogue):
    text = "W 2026 zarobisz nawet 12%."
    r = run(text, registry, catalogue, **FETCHED_2026)["R15"]
    assert r.result == "fail"
    assert r.evidence == text


def test_r15_future_tense_verb_without_figure_is_not_a_strong_marker(registry, catalogue):
    # `zarobisz` is strong only with a figure; without one, and without another marker, nothing is detected.
    assert run("Z nami zarobisz.", registry, catalogue)["R15"].result == "not_applicable"


def test_r15_fetch_year_alone_is_not_a_strong_marker(registry, catalogue):
    # Only a year after the fetch year is strong; in the fetch year a weak marker without a figure stays uncertain.
    assert run("W 2026 roku wyniki będą lepsze.", registry, catalogue, **FETCHED_2026)["R15"].result == "uncertain"


def test_r15_next_year_alone_is_a_strong_marker(registry, catalogue):
    text = "W przyszłym roku wyniki funduszu wzrosną."
    r = run(text, registry, catalogue)["R15"]
    assert r.result == "fail"
    assert r.evidence == text


def test_r15_imperative_is_not_result_vocabulary(registry, catalogue):
    # Without the imperative exclude, `zarabiaj` + `będzie` would be an uncertain forecast candidate.
    assert run("Zarabiaj z nami – będzie łatwiej.", registry, catalogue)["R15"].result == "not_applicable"


# ---- R12a period and scope ----------------------------------------------------------------------

FIVE_YEARS = "W latach 2021–2025 fundusz wypracował średnio 7% rocznie."
SOURCE = "Źródło: dane własne TFI."
FIVE_Y, REF, SRC = "5 lat / 12 mies.", "okres referencyjny", "źródło"


def test_r12a_catalogue_entry(catalogue):
    spec = catalogue.get("R12a")
    assert spec.implemented
    assert spec.legal_basis == "art. 44 ust. 4 rozp. del. 2017/565"


def test_r12a_eurotrade_one_year_without_source_fails(mock_documents, registry, catalogue):
    r = run_mock(mock_documents, EUROTRADE_ID, registry, catalogue)["R12a"]
    assert r.result == "fail"
    assert r.evidence == "Nasi klienci zarobili średnio 34% w 2025 roku."
    assert FIVE_Y in r.explanation and SRC in r.explanation
    assert REF not in r.explanation
    assert r.explanation.index(FIVE_Y) < r.explanation.index(SRC)  # fixed order


def test_r12a_five_years_with_source_passes(registry, catalogue):
    r = run(f"{FIVE_YEARS} {SOURCE}", registry, catalogue)["R12a"]
    assert r.result == "pass"
    assert r.evidence == FIVE_YEARS


@pytest.mark.parametrize(
    "short",
    ["Od początku roku fundusz zyskał 9%.", "W 3 miesiące fundusz zyskał 4%.", "W III kwartale fundusz zyskał 4%.",
     "W ostatnim miesiącu fundusz zyskał 2%.", "Wynik YTD: fundusz zyskał 5%."],
    ids=["since-start-of-year", "three-months", "quarter", "last-month", "ytd"],
)
def test_r12a_period_shorter_than_twelve_months_fails(short, registry, catalogue):
    r = run(f"{FIVE_YEARS} {short} {SOURCE}", registry, catalogue)["R12a"]
    assert r.result == "fail"
    assert r.evidence == short
    assert FIVE_Y in r.explanation and REF not in r.explanation and SRC not in r.explanation


@pytest.mark.parametrize("full", ["W ostatnich 12 miesiącach fundusz zyskał 9%.", "Przez 24 miesiące fundusz zyskał 15%."])
def test_r12a_multiple_of_twelve_months_is_a_full_period(full, registry, catalogue):
    assert run(f"{full} {FIVE_YEARS} {SOURCE}", registry, catalogue)["R12a"].result == "pass"


def test_r12a_no_reference_period_fails(registry, catalogue):
    r = run(f"Nasi klienci zarobili 34%. {SOURCE}", registry, catalogue)["R12a"]
    assert r.result == "fail"
    assert REF in r.explanation


def test_r12a_since_inception_without_date_fails_reference_period(registry, catalogue):
    text = f"Od początku działalności fundusz zarobił 18%. {SOURCE}"
    r = run(text, registry, catalogue)["R12a"]
    assert r.result == "fail"
    assert f"{REF}: niespełniony" in r.explanation
    assert f"{FIVE_Y}: do weryfikacji" in r.explanation
    assert r.explanation.index(FIVE_Y) < r.explanation.index(REF)


def test_r12a_since_inception_with_start_year_is_uncertain(registry, catalogue):
    inception = "Od uruchomienia w 2023 r. fundusz zarobił 18%."
    r = run(f"{inception} {SOURCE}", registry, catalogue)["R12a"]
    assert r.result == "uncertain"
    assert r.evidence == inception
    assert FIVE_Y in r.explanation and REF not in r.explanation and SRC not in r.explanation


@pytest.mark.parametrize(
    "text",
    ["W ciągu ostatnich 10 lat fundusz zarobił średnio 6% rocznie.",
     "Wyniki funduszu: 5% w 2021 r., 7% w 2022 r., -3% w 2023 r., 9% w 2024 r., 6% w 2025 r.",
     "Pięcioletnia stopa zwrotu funduszu za 2025 rok wyniosła 31%."],
    ids=["last-10-years", "five-distinct-years", "five-year-word"],
)
def test_r12a_five_year_coverage(text, registry, catalogue):
    assert run(f"{text} {SOURCE}", registry, catalogue)["R12a"].result == "pass"


@pytest.mark.parametrize(
    "text",
    ["W latach 2022–2025 fundusz wypracował średnio 7% rocznie.",
     "Wyniki funduszu: 7% w 2022 r., -3% w 2023 r., 9% w 2024 r., 6% w 2025 r.",
     "W ciągu ostatnich 4 lat fundusz zarobił średnio 6% rocznie."],
    ids=["four-year-range", "four-distinct-years", "last-4-years"],
)
def test_r12a_less_than_five_years_fails(text, registry, catalogue):
    r = run(f"{text} {SOURCE}", registry, catalogue)["R12a"]
    assert r.result == "fail"
    assert FIVE_Y in r.explanation and REF not in r.explanation


def test_r12a_alfa_not_applicable(mock_documents, registry, catalogue):
    r = run_mock(mock_documents, ALFA_ID, registry, catalogue)["R12a"]
    assert r.result == "not_applicable"
    assert r.evidence is None


# ---- R12b currency and costs --------------------------------------------------------------------

LIT_E = "art. 44 ust. 4 lit. e"
FEES = "Wyniki po potrąceniu opłat."
USD = "Subfundusz USD zyskał 11% w 2025 roku."  # "r." + capital stays one sentence in the splitter
FX_WARNING = "Zmiany kursów walut mogą zwiększyć lub zmniejszyć wynik."


def test_r12b_catalogue_entry(catalogue):
    spec = catalogue.get("R12b")
    assert spec.implemented
    assert spec.legal_basis == "art. 44 ust. 4 rozp. del. 2017/565"
    assert spec.llm is None  # rules-only


def test_r12b_eurotrade_fails_on_fees_only(mock_documents, registry, catalogue):
    r = run_mock(mock_documents, EUROTRADE_ID, registry, catalogue)["R12b"]
    assert r.result == "fail"
    assert r.evidence == "Nasi klienci zarobili średnio 34% w 2025 roku."
    assert "opłat" in r.explanation
    assert "kursów walut" not in r.explanation
    assert f"ostrzeżenie walutowe niewymagane – wyniki w PLN ({LIT_E})" in r.explanation


@pytest.mark.parametrize(
    "text",
    ["Fundusz zarobił 8% w 2025 r. Wyniki uwzględniają opłatę za zarządzanie.",
     "Fundusz zarobił 8% w 2025 r. Wyniki nie uwzględniają opłat i prowizji.",
     "Fundusz zarobił 8% w 2025 r. Wyniki netto, po potrąceniu kosztów."],
    ids=["includes-fee", "excludes-fees", "net"],
)
def test_r12b_fee_statement_with_pln_figures_passes(text, registry, catalogue):
    r = run(text, registry, catalogue)["R12b"]
    assert r.result == "pass"
    assert LIT_E in r.explanation


def test_r12b_foreign_currency_without_warning_fails(registry, catalogue):
    r = run(f"{USD} {FEES}", registry, catalogue)["R12b"]
    assert r.result == "fail"
    assert r.evidence == USD
    assert "kursów walut" in r.explanation and LIT_E in r.explanation
    assert "opłat" not in r.explanation


def test_r12b_foreign_currency_with_warning_passes(registry, catalogue):
    r = run(f"{USD} {FEES} {FX_WARNING}", registry, catalogue)["R12b"]
    assert r.result == "pass"
    assert LIT_E in r.explanation


def test_r12b_denominated_product_triggers_the_currency_part(registry, catalogue):
    denominated = "Fundusz jest denominowany w EUR."
    r = run(f"{denominated} Fundusz zarobił 8% w 2025 r. {FEES}", registry, catalogue)["R12b"]
    assert r.result == "fail"
    assert r.evidence == denominated


def test_r12b_both_missing_names_both(registry, catalogue):
    r = run(USD, registry, catalogue)["R12b"]
    assert r.result == "fail"
    assert "opłat" in r.explanation and "kursów walut" in r.explanation and LIT_E in r.explanation


def test_r12b_explanation_cites_lit_e_when_only_fees_are_missing(registry, catalogue):
    # Group 5 review: foreign currency with its warning, no fee statement; the explanation still cites lit. e.
    r = run(f"{USD} {FX_WARNING}", registry, catalogue)["R12b"]
    assert r.result == "fail"
    assert LIT_E in r.explanation and "opłat" in r.explanation


def test_r12b_bank_ok_not_applicable(mock_documents, registry, catalogue):
    assert run_mock(mock_documents, BANK_OK_ID, registry, catalogue)["R12b"].result == "not_applicable"


def test_missing_disclaimer_fails_only_r14(registry, catalogue):
    text = f"W latach 2021–2025 fundusz wypracował średnio 7% rocznie po potrąceniu opłat. {SOURCE}"
    results = run(text, registry, catalogue)
    assert results["R14"].result == "fail"
    assert results["R12a"].result == "pass"
    assert results["R12b"].result == "pass"


def test_shared_trigger_bank_ok_not_applicable_together(mock_documents, registry, catalogue):
    results = run_mock(mock_documents, BANK_OK_ID, registry, catalogue)
    for rule_id in ("R12a", "R12b", "R14"):
        assert results[rule_id].result == "not_applicable", rule_id
        assert results[rule_id].explanation == "Materiał nie prezentuje wyników historycznych.", rule_id


def test_forecast_is_not_past_performance_for_the_shared_trigger(registry, catalogue):
    results = run("W 2026 roku spodziewamy się 10% zysku.", registry, catalogue, **FETCHED_2026)
    assert {results[r].result for r in ("R12a", "R12b", "R14")} == {"not_applicable"}


def test_r12b_foreign_currency_outside_the_results_needs_no_warning(registry, catalogue):
    # Only a past result in a foreign currency, or a product denominated in one, needs the warning (lit. e).
    r = run("Bonus 50 USD na start. Fundusz zarobił 8% w 2025 roku. Wyniki po potrąceniu opłat.", registry, catalogue)["R12b"]
    assert r.result == "pass"
    assert "niewymagane – wyniki w PLN" in r.explanation
