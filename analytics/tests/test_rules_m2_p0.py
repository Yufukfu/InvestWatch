"""M2 P0 rules added by `analytics-llm-p0` (rules-only parts): R14, R6, R4, R17, R18.

Kept apart from `test_rules.py` so the parallel `analytics-m1-m3` change does not collide here.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from conftest import make_doc
from investwatch_analytics.models import ScrapedDocument
from investwatch_analytics.preprocessing import preprocess
from investwatch_analytics.registry import Registry
from investwatch_analytics.rules.engine import Catalogue, Context, run_rules

SEED = Path(__file__).resolve().parents[1] / "registry" / "seed.csv"

EUROTRADE = (
    "Handluj CFD na indeksy z bonusem 500 zł na start! Nasi klienci zarobili średnio 34% w 2025 roku. "
    "W przyszłym roku spodziewamy się jeszcze lepszych wyników. Risk warning: CFDs are complex instruments "
    "and come with a high risk of losing money rapidly due to leverage."
)


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


# ---- R14 past-performance disclaimer -----------------------------------------------------------


def test_r14_eurotrade_past_returns_without_disclaimer_fail(registry, catalogue):
    r = run(EUROTRADE, registry, catalogue)["R14"]
    assert r.result == "fail"
    assert r.evidence == "Nasi klienci zarobili średnio 34% w 2025 roku."
    assert r.method == "rule"


def test_r14_disclaimer_next_to_past_returns_pass(registry, catalogue):
    text = "Fundusz wypracował 12% w 2024 roku. Wyniki historyczne nie są gwarancją przyszłych wyników."
    r = run(text, registry, catalogue)["R14"]
    assert r.result == "pass"
    assert r.evidence == "Wyniki historyczne nie są gwarancją przyszłych wyników."


def test_r14_disclaimer_far_from_claim_pass(registry, catalogue):
    filler = " ".join(f"Zdanie numer {n} o ofercie." for n in range(8))
    text = f"Fundusz wypracował 12% w 2024 roku. {filler} Wyniki historyczne nie są gwarancją przyszłych wyników."
    assert run(text, registry, catalogue)["R14"].result == "pass"


def test_r14_forecast_is_not_past_performance(registry, catalogue):
    text = "W 2026 roku spodziewamy się 10% zysku."
    assert run(text, registry, catalogue, fetched_at="2026-11-21T12:00:00Z")["R14"].result == "not_applicable"


def test_r14_future_year_is_not_past_performance(registry, catalogue):
    text = "Cel: 8% rocznie do 2030 roku."
    assert run(text, registry, catalogue, fetched_at="2026-11-21T12:00:00Z")["R14"].result == "not_applicable"


def test_r14_year_up_to_fetch_year_is_past_without_verb(registry, catalogue):
    text = "Portfel ETF: +15% w 2026 roku."
    assert run(text, registry, catalogue, fetched_at="2026-11-21T12:00:00Z")["R14"].result == "fail"


def test_r14_year_after_fetch_year_is_not_past(registry, catalogue):
    text = "Portfel ETF: +15% w 2026 roku."
    assert run(text, registry, catalogue, fetched_at="2025-11-21T12:00:00Z")["R14"].result == "not_applicable"


def test_r14_footnote_only_disclaimer_passes(registry, catalogue):
    text = "Fundusz wypracował 12% w 2024 roku. *Wyniki historyczne nie są gwarancją przyszłych wyników."
    r = run(text, registry, catalogue)["R14"]
    assert r.result == "pass"
    assert r.evidence == "*Wyniki historyczne nie są gwarancją przyszłych wyników."


def test_r14_prefers_non_footnote_disclaimer_as_evidence(registry, catalogue):
    text = (
        "Fundusz wypracował 12% w 2024 roku. *Wyniki historyczne nie są gwarancją przyszłych wyników. "
        "Past performance is not a reliable indicator of future results."
    )
    r = run(text, registry, catalogue)["R14"]
    assert r.evidence == "Past performance is not a reliable indicator of future results."


@pytest.mark.parametrize("text", [
    "W ostatnich 5 latach portfel zyskał 40%.",
    "Historyczna stopa zwrotu: 9% rocznie.",
    "Nasz fundusz przyniósł 7% w zeszłym roku.",
])
def test_r14_past_markers(text, registry, catalogue):
    assert run(text, registry, catalogue)["R14"].result == "fail"


def test_r14_fee_percentage_is_not_a_return_figure(registry, catalogue):
    text = "W 2024 roku obniżyliśmy prowizja 0,1% za transakcję."
    assert run(text, registry, catalogue)["R14"].result == "not_applicable"


def test_r14_past_verb_without_figure_is_not_applicable(registry, catalogue):
    assert run("Nasi klienci zarobili dużo.", registry, catalogue)["R14"].result == "not_applicable"


# ---- evidence_locator and R6 hidden risk -------------------------------------------------------

ALFA_TEXT = (
    "Konto Premium Alfa Inwestycje. Zarabiaj nawet do 18% rocznie na portfelu ETF! "
    "Dołącz do 50 000 zadowolonych inwestorów. Działamy pod nadzorem KNF – Twoje środki są bezpieczne. "
    "Otwórz konto w 5 minut. *Inwestowanie wiąże się z ryzykiem utraty części lub całości kapitału."
)
RISK = "*Inwestowanie wiąże się z ryzykiem utraty części lub całości kapitału."


def block(text, viewport="desktop", size=20, region="main", in_view=True, visible=True, bbox=(0, 0, 100, 20), **kw):
    b = {"viewport": viewport, "text": text, "font_size_px": size, "visible": visible, "region": region,
         "in_viewport_on_load": in_view, "bbox": list(bbox) if bbox is not None else None}
    b.update(kw)
    return b


def alfa_blocks():
    return [
        block("Zarabiaj nawet do 18% rocznie na portfelu ETF!", size=44, bbox=(80, 120, 800, 60)),
        block("Działamy pod nadzorem KNF – Twoje środki są bezpieczne.", size=20, bbox=(80, 220, 700, 30)),
        block(RISK, size=9, region="footer", in_view=False, bbox=(80, 2400, 600, 12)),
        block(RISK, viewport="mobile", size=8, region="footer", in_view=False, bbox=(10, 3100, 340, 30)),
    ]


def test_evidence_locator_validates_against_contract(finding_validator):
    from investwatch_analytics.models import EvidenceLocator, RuleResult

    rr = RuleResult(rule_id="R6", name="x", result="fail", severity="high", method="rule",
                    evidence_locator=EvidenceLocator(viewport="desktop", bbox=[1, 2, 3, 4]))
    from jsonschema import Draft202012Validator

    schema = finding_validator.schema
    rule_schema = {"$defs": schema["$defs"], "$ref": "#/$defs/rule_result"}
    assert list(Draft202012Validator(rule_schema).iter_errors(rr.model_dump(mode="json"))) == []


def test_evidence_locator_rejects_bad_bbox():
    from pydantic import ValidationError

    from investwatch_analytics.models import EvidenceLocator

    with pytest.raises(ValidationError):
        EvidenceLocator(viewport="desktop", bbox=[1, 2, 3])


def test_r6_alfa_footer_below_fold_fails(registry, catalogue):
    r = run(ALFA_TEXT, registry, catalogue, blocks=alfa_blocks())["R6"]
    assert r.result == "fail" and r.evidence == RISK
    assert r.evidence_locator.viewport == "desktop" and r.evidence_locator.bbox == [80, 2400, 600, 12]


def test_r6_warning_in_main_region_passes(registry, catalogue):
    blocks = [block("Zysk 8% rocznie."), block("Inwestowanie wiąże się z ryzykiem utraty kapitału.", in_view=False)]
    text = "Zysk 8% rocznie. Inwestowanie wiąże się z ryzykiem utraty kapitału."
    assert run(text, registry, catalogue, blocks=blocks)["R6"].result == "pass"


def test_r6_footer_warning_visible_on_load_passes(registry, catalogue):
    blocks = [block("Zysk 8% rocznie."), block("Ryzyko utraty kapitału.", region="footer", in_view=True)]
    assert run("Zysk 8% rocznie. Ryzyko utraty kapitału.", registry, catalogue, blocks=blocks)["R6"].result == "pass"


def test_r6_unknown_viewport_position_is_uncertain(registry, catalogue):
    blocks = [block("Zysk 8% rocznie."), block("Ryzyko utraty kapitału.", region="legal", in_view=None)]
    r = run("Zysk 8% rocznie. Ryzyko utraty kapitału.", registry, catalogue, blocks=blocks)["R6"]
    assert r.result == "uncertain" and r.evidence == "Ryzyko utraty kapitału."


def test_r6_footnote_marker_in_main_region_is_hidden(registry, catalogue):
    blocks = [block("Zysk 8% rocznie."), block("*Ryzyko utraty kapitału.", region="main", in_view=False)]
    assert run("Zysk 8% rocznie. *Ryzyko utraty kapitału.", registry, catalogue, blocks=blocks)["R6"].result == "fail"


def test_r6_one_exposed_warning_is_enough(registry, catalogue):
    blocks = [block("Ryzyko utraty kapitału.", region="footer", in_view=False), block("Ryzyko utraty kapitału.", region="main")]
    assert run("Ryzyko utraty kapitału.", registry, catalogue, blocks=blocks)["R6"].result == "pass"


def test_r6_visibility_and_interaction_are_ignored(registry, catalogue):
    blocks = [block("Ryzyko utraty kapitału.", region="main", visible=False, requires_interaction=True)]
    assert run("Ryzyko utraty kapitału.", registry, catalogue, blocks=blocks)["R6"].result == "pass"


def test_r6_worst_viewport_decides(registry, catalogue):
    blocks = [
        block("Ryzyko utraty kapitału.", region="main"),
        block("Ryzyko utraty kapitału.", viewport="mobile", region="footer", in_view=False, bbox=(1, 2, 3, 4)),
    ]
    r = run("Ryzyko utraty kapitału.", registry, catalogue, blocks=blocks)["R6"]
    assert r.result == "fail" and r.evidence_locator.viewport == "mobile"


def test_r6_without_blocks_is_not_applicable(registry, catalogue):
    r = run(ALFA_TEXT, registry, catalogue)["R6"]
    assert r.result == "not_applicable" and r.evidence_locator is None
    assert "renderowani" in r.explanation and "brak informacji o ryzyku" not in r.explanation.lower()


def test_r6_without_risk_information_is_not_applicable(registry, catalogue):
    r = run("Zysk 8% rocznie.", registry, catalogue, blocks=[block("Zysk 8% rocznie.")])["R6"]
    assert r.result == "not_applicable" and "brak informacji o ryzyku" in r.explanation.lower()


def test_r6_denial_block_is_not_a_warning(registry, catalogue):
    blocks = [block("Inwestycja bez ryzyka.", region="footer", in_view=False)]
    r = run("Inwestycja bez ryzyka.", registry, catalogue, blocks=blocks)["R6"]
    assert r.result == "not_applicable"


def test_r6_block_text_matched_whitespace_insensitively(registry, catalogue):
    text = "Zysk 8% rocznie.\n*Inwestowanie   wiąże się\nz ryzykiem utraty kapitału."
    blocks = [block("*Inwestowanie wiąże się z ryzykiem utraty kapitału.", region="footer", in_view=False)]
    r = run(text, registry, catalogue, blocks=blocks)["R6"]
    assert r.result == "fail" and r.evidence == "*Inwestowanie   wiąże się\nz ryzykiem utraty kapitału."


def test_r6_block_text_missing_from_document_gives_null_evidence(registry, catalogue):
    blocks = [block("Ryzyko utraty kapitału.", region="footer", in_view=False)]
    r = run("Zysk 8% rocznie. Ryzyko jest.", registry, catalogue, blocks=blocks)["R6"]
    assert r.result == "fail" and r.evidence is None and r.evidence_locator.viewport == "desktop"


def test_r6_locator_without_bbox(registry, catalogue):
    blocks = [block("Ryzyko utraty kapitału.", region="footer", in_view=False, bbox=None)]
    r = run("Ryzyko utraty kapitału.", registry, catalogue, blocks=blocks)["R6"]
    assert r.evidence_locator.viewport == "desktop" and r.evidence_locator.bbox is None


def test_r14_footnote_only_disclaimer_r6_flags_placement(registry, catalogue):
    disclaimer = "*Wyniki historyczne nie są gwarancją przyszłych wyników."
    text = f"Fundusz wypracował 12% w 2024 roku. {disclaimer}"
    blocks = [block("Fundusz wypracował 12% w 2024 roku.", size=30), block(disclaimer, size=10, region="footer", in_view=False)]
    res = run(text, registry, catalogue, blocks=blocks)
    assert res["R14"].result == "pass" and res["R6"].result == "fail"


def test_r6_mock_alfa(mock_documents, registry, catalogue):
    raw = next(d for d in mock_documents if d["id"].startswith("a3c88321"))
    doc = ScrapedDocument.model_validate(raw)
    ctx = Context(doc=doc, pre=preprocess(doc.text), firm_match=registry.match(doc.text, doc.url), registry=registry)
    r = {x.rule_id: x for x in run_rules(catalogue, ctx)}["R6"]
    assert r.result == "fail" and r.evidence in doc.text


@pytest.mark.parametrize("bad", ["hiding_regions: footer", "hiding_regions: [footer, '']", "hiding_regions: [1]"])
def test_r6_bad_hiding_regions_fail_at_load(tmp_path, bad):
    from investwatch_analytics.rules.engine import CatalogueError

    src = Path(__file__).resolve().parents[1] / "src" / "investwatch_analytics" / "rules" / "m2_rules.yaml"
    text = src.read_text(encoding="utf-8")
    assert text.count("hiding_regions: [footer, legal]") == 1
    p = tmp_path / "rules.yaml"
    p.write_text(text.replace("hiding_regions: [footer, legal]", bad), encoding="utf-8")
    with pytest.raises(CatalogueError, match="hiding_regions"):
        Catalogue.load(p)


def test_r6_legal_region_counts_as_hiding(registry, catalogue):
    blocks = [block("Ryzyko utraty kapitału.", region="legal", in_view=False)]
    assert run("Ryzyko utraty kapitału.", registry, catalogue, blocks=blocks)["R6"].result == "fail"


def test_r6_hidden_plus_unknown_is_uncertain(registry, catalogue):
    blocks = [block("Ryzyko utraty kapitału.", region="footer", in_view=False),
              block("Ryzyko utraty kapitału.", region="legal", in_view=None)]
    assert run("Ryzyko utraty kapitału.", registry, catalogue, blocks=blocks)["R6"].result == "uncertain"


# ---- R14 review fixes (group 1 review) ---------------------------------------------------------


@pytest.mark.parametrize("text", [
    "Bonus 2000 zł i oprocentowanie 6%.",                         # amount, not a year
    "Promocja do 31.12.2026: oprocentowanie 7%.",                  # offer deadline
    "Lokata 6% na 12 miesięcy, oferta do końca 2026.",              # offer deadline
    "Zyskaj nawet 20% w 2026 roku!",                                # imperative promise
    "Zyskaj 20% w 2026 roku!",                                      # imperative alone
    "Lokata 7% do końca 2026 roku.",                                # deadline with a year context
    "W 2025 roku 80% klientów było zadowolonych.",                  # share of clients, not a return
    "Bonus 100% do depozytu w 2025.",                               # bonus
    "74% rachunków inwestorów detalicznych w ostatnich 12 miesiącach odnotowało straty.",  # ESMA warning
])
def test_r14_non_past_performance(text, registry, catalogue):
    assert run(text, registry, catalogue, fetched_at="2026-11-21T12:00:00Z")["R14"].result == "not_applicable"


@pytest.mark.parametrize("disclaimer", [
    "Osiągnięte w przeszłości wyniki nie gwarantują osiągnięcia podobnych w przyszłości.",
    "Past results are not indicative of future results.",
    "Historical returns are not indicative of future returns.",
])
def test_r14_more_disclaimer_wordings(disclaimer, registry, catalogue):
    text = f"Fundusz wypracował 12% w 2024 roku. {disclaimer}"
    assert run(text, registry, catalogue)["R14"].result == "pass"


def test_r14_past_marker_beats_future_marker_in_one_sentence(registry, catalogue):
    text = "Nasz fundusz zarobił w 2025 roku 12%, a w 2026 roku celujemy w 15%."
    assert run(text, registry, catalogue, fetched_at="2026-11-21T12:00:00Z")["R14"].result == "fail"


def test_r14_year_suffix_form_counts(registry, catalogue):
    text = "Portfel ETF: 2025 rok zamknięty wynikiem +11%."
    assert run(text, registry, catalogue, fetched_at="2026-11-21T12:00:00Z")["R14"].result == "fail"


def test_r14_year_with_context_still_counts(registry, catalogue):
    assert run("Za 2025 r. portfel: +11%.", registry, catalogue, fetched_at="2026-11-21T12:00:00Z")["R14"].result == "fail"


# ---- R4 risk font size -------------------------------------------------------------------------


def test_weighted_median():
    from investwatch_analytics.rules.m2 import weighted_median

    assert weighted_median([(9, 70), (20, 55), (44, 46)]) == 20
    assert weighted_median([(20, 1), (10, 1)]) == 10
    assert weighted_median([(12, 5)]) == 12


def test_r4_alfa_small_footer_warning_fails(registry, catalogue):
    r = run(ALFA_TEXT, registry, catalogue, blocks=alfa_blocks())["R4"]
    assert r.result == "fail" and r.evidence == RISK
    assert "9 px" in r.explanation and "20 px" in r.explanation and "0,45" in r.explanation
    assert r.evidence_locator.viewport == "desktop" and r.evidence_locator.bbox == [80, 2400, 600, 12]


def test_r4_readable_warning_passes(registry, catalogue):
    blocks = [block("Zysk 8% rocznie na koncie.", size=20), block("Ryzyko utraty kapitału.", size=18)]
    r = run("Zysk 8% rocznie na koncie. Ryzyko utraty kapitału.", registry, catalogue, blocks=blocks)["R4"]
    assert r.result == "pass" and r.evidence == "Ryzyko utraty kapitału."


def test_r4_ratio_at_threshold_passes(registry, catalogue):
    blocks = [block("Zysk 8% rocznie na naszym koncie maklerskim.", size=20), block("Ryzyko utraty.", size=15)]
    assert run("Zysk 8% rocznie na naszym koncie maklerskim. Ryzyko utraty.", registry, catalogue, blocks=blocks)["R4"].result == "pass"


def test_r4_ratio_just_below_threshold_fails(registry, catalogue):
    blocks = [block("Zysk 8% rocznie na naszym koncie maklerskim.", size=20), block("Ryzyko utraty.", size=14.9)]
    assert run("Zysk 8% rocznie na naszym koncie maklerskim. Ryzyko utraty.", registry, catalogue, blocks=blocks)["R4"].result == "fail"


def test_r4_largest_risk_block_is_judged(registry, catalogue):
    blocks = [block("Zysk 8% rocznie na koncie.", size=20), block("Ryzyko utraty.", size=8),
              block("Ryzyko utraty kapitału.", size=19)]
    r = run("Zysk 8% rocznie na koncie. Ryzyko utraty. Ryzyko utraty kapitału.", registry, catalogue, blocks=blocks)["R4"]
    assert r.result == "pass" and r.evidence == "Ryzyko utraty kapitału."


def test_r4_invisible_blocks_do_not_count(registry, catalogue):
    blocks = [block("Zysk 8% rocznie na koncie.", size=20), block("Ryzyko utraty kapitału.", size=19),
              block("Ukryty tekst " * 30, size=60, visible=False)]
    assert run("Zysk 8% rocznie na koncie. Ryzyko utraty kapitału.", registry, catalogue, blocks=blocks)["R4"].result == "pass"


def test_r4_without_blocks_is_not_applicable(registry, catalogue):
    from investwatch_analytics.rules.m2 import NO_BLOCKS

    r = run(ALFA_TEXT, registry, catalogue)["R4"]
    assert r.result == "not_applicable" and r.explanation == NO_BLOCKS


def test_r4_without_risk_information_is_not_applicable(registry, catalogue):
    r = run("Zysk 8% rocznie.", registry, catalogue, blocks=[block("Zysk 8% rocznie.")])["R4"]
    assert r.result == "not_applicable" and "brak informacji o ryzyku" in r.explanation.lower()


def test_r4_risk_only_in_invisible_block_is_not_applicable(registry, catalogue):
    blocks = [block("Zysk 8% rocznie."), block("Ryzyko utraty kapitału.", size=6, visible=False)]
    r = run("Zysk 8% rocznie. Ryzyko utraty kapitału.", registry, catalogue, blocks=blocks)["R4"]
    assert r.result == "not_applicable" and "R5" in r.explanation


def test_r4_worst_viewport_decides(registry, catalogue):
    text = "Zysk 8% rocznie na koncie. Ryzyko utraty kapitału."
    blocks = [
        block("Zysk 8% rocznie na koncie.", size=20), block("Ryzyko utraty kapitału.", size=18),
        block("Zysk 8% rocznie na koncie.", viewport="mobile", size=20),
        block("Ryzyko utraty kapitału.", viewport="mobile", size=10, bbox=(1, 2, 3, 4)),
    ]
    r = run(text, registry, catalogue, blocks=blocks)["R4"]
    assert r.result == "fail" and r.evidence_locator.viewport == "mobile" and "0,50" in r.explanation


@pytest.mark.parametrize("bad", ["min_ratio: 0", "min_ratio: 1.5", "min_ratio: x", "min_ratio: true", "min_ratio: -0.5"])
def test_r4_bad_min_ratio_fails_at_load(tmp_path, bad):
    from investwatch_analytics.rules.engine import CatalogueError

    src = Path(__file__).resolve().parents[1] / "src" / "investwatch_analytics" / "rules" / "m2_rules.yaml"
    text = src.read_text(encoding="utf-8")
    assert text.count("min_ratio: 0.75") == 1
    p = tmp_path / "rules.yaml"
    p.write_text(text.replace("min_ratio: 0.75", bad), encoding="utf-8")
    with pytest.raises(CatalogueError, match="min_ratio"):
        Catalogue.load(p)


def test_r4_min_ratio_one_is_allowed(tmp_path):
    src = Path(__file__).resolve().parents[1] / "src" / "investwatch_analytics" / "rules" / "m2_rules.yaml"
    p = tmp_path / "rules.yaml"
    p.write_text(src.read_text(encoding="utf-8").replace("min_ratio: 0.75", "min_ratio: 1"), encoding="utf-8")
    assert Catalogue.load(p).get("R4").params["min_ratio"] == 1


# ---- group 2 review fixes ----------------------------------------------------------------------


@pytest.mark.parametrize("text", [
    "Inwestuj od 2000 zł i odbierz 8% w skali roku.",
    "Zacznij z 2000 zł, oprocentowanie 6%.",
    "Lokata za 2000 PLN: 5% w skali roku.",
])
def test_r14_amount_after_preposition_is_not_a_year(text, registry, catalogue):
    assert run(text, registry, catalogue, fetched_at="2026-11-21T12:00:00Z")["R14"].result == "not_applicable"


def test_r14_vazne_heading_does_not_hide_past_performance(registry, catalogue):
    text = "Ważne: fundusz dał 12% w 2024 r."
    assert run(text, registry, catalogue, fetched_at="2026-11-21T12:00:00Z")["R14"].result == "fail"


def test_r14_offer_valid_until_is_future(registry, catalogue):
    text = "Oferta ważna do 2026 roku: 7%."
    assert run(text, registry, catalogue, fetched_at="2026-11-21T12:00:00Z")["R14"].result == "not_applicable"


def test_r6_evidence_is_the_warning_sentence_not_the_whole_block(registry, catalogue):
    footer = "Alfa Inwestycje DM S.A., ul. Prosta 1, Warszawa. Inwestowanie wiąże się z ryzykiem utraty kapitału."
    text = f"Zysk 8% rocznie. {footer}"
    blocks = [block("Zysk 8% rocznie."), block(footer, region="footer", in_view=False)]
    res = run(text, registry, catalogue, blocks=blocks)
    assert res["R6"].evidence == "Inwestowanie wiąże się z ryzykiem utraty kapitału."
    assert res["R4"].evidence == "Inwestowanie wiąże się z ryzykiem utraty kapitału."


def test_r14_vazne_heading_with_year_only(registry, catalogue):
    text = "Ważne: portfel +12% w 2024 r."
    assert run(text, registry, catalogue, fetched_at="2026-11-21T12:00:00Z")["R14"].result == "fail"


def test_r6_quote_comes_from_inside_the_block(registry, catalogue):
    footer = "Alfa Inwestycje DM S.A., Warszawa. Inwestowanie wiąże się z ryzykiem utraty kapitału."
    text = f"Ryzyko jest po naszej stronie. Zysk 8% rocznie. {footer}"
    blocks = [block("Zysk 8% rocznie."), block(footer, region="footer", in_view=False)]
    r = run(text, registry, catalogue, blocks=blocks)["R6"]
    assert r.evidence == "Inwestowanie wiąże się z ryzykiem utraty kapitału."


# ---- R17 / R18, rules-only part; catalogue `llm:` blocks ----------------------------------------

BANK_TEXT = (
    "Reklama. Bank Przykładowy S.A. – Biuro Maklerskie. Otwórz IKE i inwestuj długoterminowo. "
    "Inwestowanie w instrumenty finansowe wiąże się z ryzykiem utraty części lub całości zainwestowanego kapitału. "
    "Traktowanie podatkowe zależy od indywidualnej sytuacji klienta i może ulec zmianie."
)
ALFA_KNF = "Działamy pod nadzorem KNF – Twoje środki są bezpieczne."


def test_r17_explicit_approval_fails(registry, catalogue):
    r = run("Reklama. Produkt zatwierdzony przez KNF. Zysk 5%.", registry, catalogue)["R17"]
    assert r.result == "fail" and r.evidence == "Produkt zatwierdzony przez KNF." and r.method == "rule"


def test_r17_bare_mention_passes_rules_only(registry, catalogue):
    r = run(ALFA_TEXT, registry, catalogue)["R17"]
    assert r.result == "pass" and r.evidence == ALFA_KNF and r.method == "rule"


def test_r17_no_supervisor_is_not_applicable(registry, catalogue):
    assert run(BANK_TEXT, registry, catalogue)["R17"].result == "not_applicable"


def test_r17_approval_word_in_another_sentence_does_not_fail(registry, catalogue):
    text = "Jesteśmy nadzorowani przez KNF. Nasz produkt został zatwierdzony przez zarząd."
    assert run(text, registry, catalogue)["R17"].result == "pass"


@pytest.mark.parametrize("text", [
    "Fundusz rekomendowany przez Komisję Nadzoru Finansowego.",
    "Approved by ESMA for retail investors.",
    "Platforma z certyfikatem KNF.",
])
def test_r17_approval_variants(text, registry, catalogue):
    assert run(text, registry, catalogue)["R17"].result == "fail"


def test_r18_same_sentence_fails(registry, catalogue):
    r = run(ALFA_TEXT, registry, catalogue)["R18"]
    assert r.result == "fail" and r.evidence == ALFA_KNF and r.method == "rule"


def test_r18_zasob_example_fails(registry, catalogue):
    text = "Inwestycja w pełni bezpieczna – spełniamy rygorystyczne wymogi nadzorcze KNF."
    r = run(text, registry, catalogue)["R18"]
    assert r.result == "fail" and r.evidence == text


def test_r18_neighbouring_sentence_is_uncertain(registry, catalogue):
    text = "Jesteśmy nadzorowani przez KNF. Twoje pieniądze są u nas bezpieczne."
    r = run(text, registry, catalogue)["R18"]
    assert r.result == "uncertain" and r.evidence == "Jesteśmy nadzorowani przez KNF."


def test_r18_safety_word_two_sentences_away_passes(registry, catalogue):
    text = "Jesteśmy nadzorowani przez KNF. Otwórz konto w 5 minut. Twoje pieniądze są u nas bezpieczne."
    assert run(text, registry, catalogue)["R18"].result == "pass"


def test_r18_neutral_legal_footer_passes(registry, catalogue):
    text = "Zysk 5% rocznie. Dom Maklerski podlega nadzorowi Komisji Nadzoru Finansowego."
    r = run(text, registry, catalogue)["R18"]
    assert r.result == "pass" and r.evidence == "Dom Maklerski podlega nadzorowi Komisji Nadzoru Finansowego."


def test_r18_no_supervisor_is_not_applicable(registry, catalogue):
    assert run("Twoje środki są bezpieczne.", registry, catalogue)["R18"].result == "not_applicable"


def test_r18_pewnego_is_not_a_safety_word(registry, catalogue):
    text = "Pewnego dnia dołączyliśmy do rynku nadzorowanego przez KNF."
    assert run(text, registry, catalogue)["R18"].result == "pass"


def test_llm_blocks_only_on_the_refined_rules(catalogue):
    with_llm = [s.id for s in catalogue.specs if s.llm is not None]
    assert with_llm == ["R3", "R9", "R11", "R12a", "R15", "R17", "R18"]  # R9: analytics-m2-text-rules
    assert all(catalogue.get(i).llm["question"].strip() for i in with_llm)
    assert catalogue.get("R17").llm["when"] == "always"


def _catalogue_text() -> str:
    src = Path(__file__).resolve().parents[1] / "src" / "investwatch_analytics" / "rules" / "m2_rules.yaml"
    return src.read_text(encoding="utf-8")


@pytest.mark.parametrize("bad", [
    "    llm: {question: '', when: always}\n",
    "    llm: {question: 'Czy?', when: sometimes}\n",
    "    llm: 'Czy?'\n",
    "    llm: {question: 'Czy?', when: always, model: x}\n",
])
def test_bad_llm_block_fails_at_load(tmp_path, bad):
    from investwatch_analytics.rules.engine import CatalogueError

    text = _catalogue_text()
    anchor = "  - id: R1\n    name: Identyfikacja firmy\n"
    assert text.count(anchor) == 1
    p = tmp_path / "rules.yaml"
    p.write_text(text.replace(anchor, anchor + bad), encoding="utf-8")
    with pytest.raises(CatalogueError, match="R1.*llm"):
        Catalogue.load(p)


def test_llm_block_must_be_a_mapping(tmp_path):
    from investwatch_analytics.rules.engine import CatalogueError

    anchor = "  - id: R1\n    name: Identyfikacja firmy\n"
    p = tmp_path / "rules.yaml"
    p.write_text(_catalogue_text().replace(anchor, anchor + "    llm: 'Czy?'\n"), encoding="utf-8")
    with pytest.raises(CatalogueError, match="R1 llm must be a mapping"):
        Catalogue.load(p)


def test_llm_when_defaults_to_uncertain(tmp_path):
    text = _catalogue_text()
    anchor = "  - id: R1\n    name: Identyfikacja firmy\n"
    p = tmp_path / "rules.yaml"
    p.write_text(text.replace(anchor, anchor + "    llm: {question: 'Czy firma jest podana?'}\n"), encoding="utf-8")
    assert Catalogue.load(p).get("R1").llm == {"question": "Czy firma jest podana?", "when": "uncertain"}


# ---- group 3 review fixes ----------------------------------------------------------------------


def test_r14_tysiace_after_year_is_still_a_year(registry, catalogue):
    text = "W 2023 tysiące klientów: +8%."
    assert run(text, registry, catalogue, fetched_at="2026-11-21T12:00:00Z")["R14"].result == "fail"


def test_r14_thousands_abbreviation_is_an_amount(registry, catalogue):
    text = "Inwestuj od 2000 tys. zł i odbierz 8% w skali roku."
    assert run(text, registry, catalogue, fetched_at="2026-11-21T12:00:00Z")["R14"].result == "not_applicable"


def test_r4_zero_px_blocks_do_not_set_the_dominant_size(registry, catalogue):
    body = "Zysk 8% rocznie na naszym koncie maklerskim przez cały rok."
    blocks = [block("Zysk " * 30, size=0), block(body, size=20), block("Ryzyko utraty kapitału.", size=9)]
    r = run(f"{body} Ryzyko utraty kapitału.", registry, catalogue, blocks=blocks)["R4"]
    assert r.result == "fail" and "20 px" in r.explanation


def test_r4_only_zero_px_text_is_uncertain(registry, catalogue):
    blocks = [block("Zysk " * 5, size=0), block("Ryzyko utraty kapitału.", size=0)]
    r = run("Ryzyko utraty kapitału.", registry, catalogue, blocks=blocks)["R4"]
    assert r.result == "uncertain"


def test_r4_displayed_ratio_never_contradicts_the_verdict(registry, catalogue):
    blocks = [block("Zysk 8% rocznie na naszym koncie maklerskim.", size=20), block("Ryzyko utraty.", size=14.99)]
    r = run("Zysk 8% rocznie na naszym koncie maklerskim. Ryzyko utraty.", registry, catalogue, blocks=blocks)["R4"]
    assert r.result == "fail" and "0,749" in r.explanation


# ---- group 4 review fixes ----------------------------------------------------------------------


@pytest.mark.parametrize("text", [
    "KNF nie zaaprobował tego produktu.",
    "Komisja Nadzoru Finansowego nie zatwierdza materiałów reklamowych.",
    "Zatwierdzenie prospektu przez KNF nie powinno być rozumiane jako poparcie dla oferowanych akcji.",
    "Spółka posiada certyfikat ISO 27001 i podlega nadzorowi KNF.",
])
def test_r17_lawful_or_negated_wording_is_not_a_rules_fail(text, registry, catalogue):
    assert run(text, registry, catalogue)["R17"].result == "pass"


@pytest.mark.parametrize("text", [
    "Rada Nadzorcza zatwierdziła wypłatę dywidendy.",
    "Kup licencję na oprogramowanie.",
    "Rynek regulowany GPW.",
    "Twój portfel nadzorowany przez doświadczonych zarządzających jest bezpieczny.",
])
def test_non_supervisor_words_are_not_mentions(text, registry, catalogue):
    res = run(text, registry, catalogue)
    assert res["R17"].result == "not_applicable" and res["R18"].result == "not_applicable"


@pytest.mark.parametrize("text", [
    "Licencja KNF na prowadzenie działalności maklerskiej.",
    "Posiadamy licencję maklerską.",
    "Podmiot regulowany przez CySEC.",
    "Fundusz nadzorowany przez Komisję Nadzoru Finansowego.",
])
def test_real_supervisor_mentions_still_count(text, registry, catalogue):
    assert run(text, registry, catalogue)["R17"].result == "pass"


@pytest.mark.parametrize("text", [
    "Bezpieczeństwo Twoich środków gwarantuje nadzór KNF.",
    "Nadzór KNF gwarantuje, że Twoje środki nie przepadną.",
    "Bezpieczeństwo Twoich środków to nadzór KNF.",
])
def test_r18_more_safety_wordings(text, registry, catalogue):
    assert run(text, registry, catalogue)["R18"].result == "fail"


def test_r18_negated_guarantee_is_not_a_safety_argument(registry, catalogue):
    text = "Nadzór KNF nie gwarantuje bezpieczeństwa inwestycji."
    assert run(text, registry, catalogue)["R18"].result == "pass"


@pytest.mark.parametrize("bad", ["[always]", "{a: 1}"])
def test_llm_when_unhashable_fails_cleanly(tmp_path, bad):
    from investwatch_analytics.rules.engine import CatalogueError

    anchor = "  - id: R1\n    name: Identyfikacja firmy\n"
    p = tmp_path / "rules.yaml"
    p.write_text(_catalogue_text().replace(anchor, anchor + f"    llm: {{question: 'Czy?', when: {bad}}}\n"), encoding="utf-8")
    with pytest.raises(CatalogueError, match="R1 llm.when"):
        Catalogue.load(p)


# ---- coordinator answers (follow-ups R9, R18, R31) ----------------------------------------------


def test_r18_compensation_scheme_fact_passes(registry, catalogue):
    text = "Fundusz nadzorowany przez KNF, środki chronione przez system rekompensat."
    assert run(text, registry, catalogue)["R18"].result == "pass"


def test_r18_compensation_plus_safety_claim_still_fails(registry, catalogue):
    text = "Nadzór KNF i system rekompensat sprawiają, że inwestycja jest w pełni bezpieczna."
    assert run(text, registry, catalogue)["R18"].result == "fail"


@pytest.mark.parametrize("text", [
    "Nasi klienci zarobili 5 000 zł.",
    "Zysk 1200 PLN w 2025 roku.",
    "Portfel przyniósł 3 500 zł w ostatnich 12 miesiącach.",
])
def test_r14_absolute_amount_past_performance(text, registry, catalogue):
    assert run(text, registry, catalogue, fetched_at="2026-11-21T12:00:00Z")["R14"].result == "fail"


@pytest.mark.parametrize("text", [
    "Bonus 500 zł na start w 2025 roku.",
    "Abonament 990 zł miesięcznie od 2025 roku.",
    "Zarabiaj nawet 5 000 zł miesięcznie!",
])
def test_r14_amounts_without_past_return_are_not_past_performance(text, registry, catalogue):
    assert run(text, registry, catalogue, fetched_at="2026-11-21T12:00:00Z")["R14"].result == "not_applicable"


def test_r6_missing_region_is_never_pass(registry, catalogue):
    blocks = [block("Zysk 8% rocznie.", region=None, in_view=None), block("Ryzyko utraty kapitału.", region=None, in_view=None)]
    r = run("Zysk 8% rocznie. Ryzyko utraty kapitału.", registry, catalogue, blocks=blocks)["R6"]
    assert r.result == "not_applicable" and "brak metadanych renderowania" in r.explanation.lower()


def test_r6_missing_region_but_in_view_passes(registry, catalogue):
    blocks = [block("Ryzyko utraty kapitału.", region=None, in_view=True)]
    assert run("Ryzyko utraty kapitału.", registry, catalogue, blocks=blocks)["R6"].result == "pass"


def test_r6_missing_region_with_partial_evidence_is_uncertain(registry, catalogue):
    blocks = [block("Ryzyko utraty kapitału.", region="footer", in_view=False),
              block("Ryzyko utraty kapitału.", region=None, in_view=False)]
    assert run("Ryzyko utraty kapitału.", registry, catalogue, blocks=blocks)["R6"].result == "uncertain"


def test_r6_footnote_with_missing_region_is_judged_by_marker(registry, catalogue):
    blocks = [block("*Ryzyko utraty kapitału.", region=None, in_view=False)]
    assert run("*Ryzyko utraty kapitału.", registry, catalogue, blocks=blocks)["R6"].result == "fail"


def test_r6_missing_metadata_in_one_viewport_does_not_hide_the_other(registry, catalogue):
    blocks = [block("Ryzyko utraty kapitału.", region="footer", in_view=False),
              block("Ryzyko utraty kapitału.", viewport="mobile", region=None, in_view=None)]
    assert run("Ryzyko utraty kapitału.", registry, catalogue, blocks=blocks)["R6"].result == "fail"


def test_visual_rules_without_blocks_on_every_mock(mock_documents, registry, catalogue):
    for raw in mock_documents:
        raw = {**raw, "blocks": []}
        doc = ScrapedDocument.model_validate(raw)
        ctx = Context(doc=doc, pre=preprocess(doc.text), firm_match=registry.match(doc.text, doc.url), registry=registry)
        res = {r.rule_id: r.result for r in run_rules(catalogue, ctx)}
        assert res["R4"] == "not_applicable" and res["R6"] == "not_applicable"


# ---- adversarial input (ReDoS) -----------------------------------------------------------------

import time  # noqa: E402


@pytest.mark.parametrize("text", [
    "1" * 20000,                       # digit run: \d+...% was quadratic
    "1" * 20000 + "%",
    "1," * 10000,
    "Zysk " + "9" * 20000 + " zł w 2025 roku.",
])
def test_rules_are_linear_on_long_digit_runs(text, registry, catalogue):
    start = time.perf_counter()
    run(text, registry, catalogue)
    assert time.perf_counter() - start < 2.0


def test_locate_caps_whitespace_insensitive_search():
    from investwatch_analytics.rules.m2 import locate

    start = time.perf_counter()
    assert locate("a " * 40000, "a " * 3000 + "b") is None
    assert time.perf_counter() - start < 0.5
    assert locate("x  y\nz", "x y z") == "x  y\nz"
