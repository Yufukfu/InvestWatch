"""Visual M2 rules R5, R7, R8 and R13 (change `analytics-m2-visual-rules`), read from rendered `blocks`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest import make_doc
from investwatch_analytics.models import ScrapedDocument
from investwatch_analytics.preprocessing import preprocess
from investwatch_analytics.registry import Registry
from investwatch_analytics.rules.engine import Catalogue, CatalogueError, Context, run_rules

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "registry" / "seed.csv"
GOLD = ROOT / "eval" / "gold.jsonl"
CATALOGUE = ROOT / "src" / "investwatch_analytics" / "rules" / "m2_rules.yaml"

RISK = "Inwestowanie w instrumenty finansowe wiąże się z ryzykiem utraty części lub całości kapitału."
HEAD = "Konto maklerskie dla każdego"
TEXT = f"{HEAD}. Reklama. {RISK}"


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


def gold(gold_id: str) -> dict:
    for line in GOLD.read_text(encoding="utf-8").splitlines():
        item = json.loads(line)
        if item["id"] == gold_id:
            return item["document"]
    raise KeyError(gold_id)


def run_gold(gold_id: str, registry: Registry, catalogue: Catalogue) -> dict:
    doc = ScrapedDocument.model_validate(gold(gold_id))
    ctx = Context(doc=doc, pre=preprocess(doc.text), firm_match=registry.match(doc.text, doc.url), registry=registry)
    return {r.rule_id: r for r in run_rules(catalogue, ctx)}


def block(text, viewport="desktop", size=16, visible=True, color="#222222", background="#ffffff",
          interaction=False, clipped=False, bbox=None, **kw):
    b = {"viewport": viewport, "text": text, "font_size_px": size, "visible": visible, "color": color,
         "background_color": background, "requires_interaction": interaction, "overflow_clipped": clipped,
         "region": "main", "in_viewport_on_load": True, "bbox": list(bbox) if bbox is not None else None}
    b.update(kw)
    return b


def page(risk_desktop: dict | None = None, risk_mobile: dict | None = None) -> list[dict]:
    """A heading and a risk block on desktop and mobile; the dicts override the risk block's fields."""
    blocks = [block(HEAD, size=32), block(HEAD, viewport="mobile", size=24)]
    if risk_desktop is not False:
        blocks.append(block(RISK, **(risk_desktop or {})))
    if risk_mobile is not False:
        blocks.append(block(RISK, **{"viewport": "mobile", "size": 14, **(risk_mobile or {})}))
    return blocks


def test_catalogue_implements_the_visual_rules(catalogue):
    implemented = {s.id for s in catalogue.implemented}
    assert {"R5", "R7", "R8", "R13"} <= implemented


# ---- R5 exposure and contrast ------------------------------------------------------------------


def test_r5_gold_low_contrast_fails(registry, catalogue):
    r = run_gold("m2-r5-low-contrast", registry, catalogue)["R5"]
    assert r.result == "fail"
    assert r.evidence == RISK.replace("kapitału", "zainwestowanego kapitału")
    assert r.evidence_locator is not None and r.evidence_locator.viewport == "desktop"
    assert "1,54" in r.explanation and "4,5" in r.explanation


def test_r5_low_contrast_on_mobile_only_reports_mobile(registry, catalogue):
    r = run(TEXT, registry, catalogue, blocks=page(risk_mobile={"color": "#cccccc"}))["R5"]
    assert r.result == "fail"
    assert r.evidence == RISK
    assert r.evidence_locator.viewport == "mobile"


def test_r5_hidden_warning_fails(registry, catalogue):
    r = run(TEXT, registry, catalogue, blocks=page(risk_desktop={"visible": False}))["R5"]
    assert r.result == "fail"
    assert "niewidoczne" in r.explanation


def test_r5_readable_warning_passes(registry, catalogue):
    r = run(TEXT, registry, catalogue, blocks=page())["R5"]
    assert r.result == "pass"
    assert r.evidence == RISK


def test_r5_one_exposed_warning_per_viewport_is_enough(registry, catalogue):
    blocks = page() + [block(RISK, visible=False), block(RISK, color="#eeeeee")]
    assert run(TEXT, registry, catalogue, blocks=blocks)["R5"].result == "pass"


@pytest.mark.parametrize("field", ["color", "background"])
@pytest.mark.parametrize("value", [None, "#fff", "rgb(0, 0, 0)"])
def test_r5_unknown_colours_are_uncertain(registry, catalogue, field, value):
    r = run(TEXT, registry, catalogue, blocks=page(risk_desktop={field: value}))["R5"]
    assert r.result == "uncertain"


def test_r5_unknown_colours_never_hide_a_failing_viewport(registry, catalogue):
    blocks = page(risk_desktop={"color": None}, risk_mobile={"visible": False})
    assert run(TEXT, registry, catalogue, blocks=blocks)["R5"].result == "fail"


def test_r5_contrast_boundary(registry, catalogue):
    # #767676 on white is 4.54:1 (passes AA); #777777 is 4.48:1 (fails).
    assert run(TEXT, registry, catalogue, blocks=page(risk_desktop={"color": "#767676"}))["R5"].result == "pass"
    assert run(TEXT, registry, catalogue, blocks=page(risk_desktop={"color": "#777777"}))["R5"].result == "fail"


def test_r5_without_blocks_is_not_applicable(registry, catalogue):
    r = run(TEXT, registry, catalogue)["R5"]
    assert r.result == "not_applicable"
    assert r.evidence is None
    assert "renderowaniu" in r.explanation


def test_r5_without_risk_information_is_not_applicable(registry, catalogue):
    r = run(f"{HEAD}. Reklama.", registry, catalogue, blocks=[block(HEAD, size=32)])["R5"]
    assert r.result == "not_applicable"
    assert "brak informacji o ryzyku" in r.explanation.lower()


@pytest.mark.parametrize("bad", ["min_contrast: 0.5", "min_contrast: 22", "min_contrast: x", "min_contrast: true"])
def test_r5_bad_min_contrast_fails_at_load(tmp_path, bad):
    text = CATALOGUE.read_text(encoding="utf-8")
    assert text.count("min_contrast: 4.5") == 1
    p = tmp_path / "m2.yaml"
    p.write_text(text.replace("min_contrast: 4.5", bad), encoding="utf-8")
    with pytest.raises(CatalogueError, match="R5 min_contrast"):
        Catalogue.load(p)


def test_r5_evidence_is_the_warning_sentence_inside_the_block(registry, catalogue):
    blocks = [block(HEAD, size=32), block(f"Reklama. {RISK}", color="#dddddd")]
    r = run(TEXT, registry, catalogue, blocks=blocks)["R5"]
    assert r.result == "fail"
    assert r.evidence == RISK


# ---- R7 one-click availability -----------------------------------------------------------------


def test_r7_gold_risk_behind_click_fails(registry, catalogue):
    r = run_gold("m2-r7-risk-behind-click", registry, catalogue)["R7"]
    assert r.result == "fail"
    assert r.evidence == RISK.replace("kapitału", "zainwestowanego kapitału")
    assert r.evidence_locator.viewport == "desktop"
    assert "kliknięcia" in r.explanation


def test_r7_warning_on_the_page_passes(registry, catalogue):
    r = run(TEXT, registry, catalogue, blocks=page())["R7"]
    assert r.result == "pass"
    assert r.evidence == RISK


def test_r7_behind_click_on_mobile_only_fails_on_mobile(registry, catalogue):
    r = run(TEXT, registry, catalogue, blocks=page(risk_mobile={"interaction": True}))["R7"]
    assert r.result == "fail"
    assert r.evidence_locator.viewport == "mobile"


def test_r7_one_reachable_warning_is_enough(registry, catalogue):
    blocks = page() + [block(RISK, interaction=True)]
    assert run(TEXT, registry, catalogue, blocks=blocks)["R7"].result == "pass"


def test_r7_without_interaction_metadata_is_not_applicable(registry, catalogue):
    blocks = page(risk_desktop={"interaction": None}, risk_mobile={"interaction": None})
    r = run(TEXT, registry, catalogue, blocks=blocks)["R7"]
    assert r.result == "not_applicable"
    assert "brak metadanych renderowania" in r.explanation.lower()


def test_r7_partly_unknown_interaction_is_uncertain(registry, catalogue):
    blocks = page(risk_desktop={"interaction": True}) + [block(RISK, interaction=None)]
    assert run(TEXT, registry, catalogue, blocks=blocks)["R7"].result == "uncertain"


def test_r7_unknown_viewport_does_not_hide_a_failing_one(registry, catalogue):
    blocks = page(risk_desktop={"interaction": None}, risk_mobile={"interaction": True})
    assert run(TEXT, registry, catalogue, blocks=blocks)["R7"].result == "fail"


def test_r7_without_blocks_or_risk_is_not_applicable(registry, catalogue):
    r = run(TEXT, registry, catalogue)["R7"]
    assert r.result == "not_applicable" and "renderowaniu" in r.explanation
    r = run(f"{HEAD}. Reklama.", registry, catalogue, blocks=[block(HEAD, size=32)])["R7"]
    assert r.result == "not_applicable"
    assert "brak informacji o ryzyku" in r.explanation.lower()


# ---- R8 responsiveness -------------------------------------------------------------------------


def test_r8_gold_missing_on_mobile_fails(registry, catalogue):
    r = run_gold("m2-r8-risk-missing-on-mobile", registry, catalogue)["R8"]
    assert r.result == "fail"
    assert r.evidence_locator.viewport == "mobile"
    assert "mobile" in r.explanation
    assert r.evidence == RISK.replace("kapitału", "zainwestowanego kapitału")  # quoted from the other viewport


def test_r8_gold_small_font_fails(registry, catalogue):
    r = run_gold("m2-r4-small-risk-font", registry, catalogue)["R8"]
    assert r.result == "fail"
    assert "9 px" in r.explanation and "12 px" in r.explanation


def test_r8_hidden_on_every_viewport_fails(registry, catalogue):
    assert run_gold("m2-r7-risk-behind-click", registry, catalogue)["R8"].result == "fail"


def test_r8_clipped_mobile_warning_fails(registry, catalogue):
    r = run(TEXT, registry, catalogue, blocks=page(risk_mobile={"clipped": True}))["R8"]
    assert r.result == "fail"
    assert r.evidence_locator.viewport == "mobile"
    assert r.evidence == RISK


def test_r8_font_boundary(registry, catalogue):
    assert run(TEXT, registry, catalogue, blocks=page(risk_mobile={"size": 12}))["R8"].result == "pass"
    assert run(TEXT, registry, catalogue, blocks=page(risk_mobile={"size": 11.5}))["R8"].result == "fail"


def test_r8_responsive_warning_passes(registry, catalogue):
    r = run(TEXT, registry, catalogue, blocks=page())["R8"]
    assert r.result == "pass"
    assert r.evidence == RISK


def test_r8_one_readable_block_per_viewport_is_enough(registry, catalogue):
    blocks = page() + [block(RISK, viewport="mobile", size=8, clipped=True)]
    assert run(TEXT, registry, catalogue, blocks=blocks)["R8"].result == "pass"


def test_r8_unknown_clipping_is_uncertain(registry, catalogue):
    r = run(TEXT, registry, catalogue, blocks=page(risk_mobile={"clipped": None}))["R8"]
    assert r.result == "uncertain"


def test_r8_one_viewport_only(registry, catalogue):
    r = run(TEXT, registry, catalogue, blocks=page(risk_mobile=False)[:1] + [block(RISK)])["R8"]
    assert r.result == "uncertain"
    assert "jednym widoku" in r.explanation
    small = [block(HEAD, size=32), block(RISK, size=9)]
    assert run(TEXT, registry, catalogue, blocks=small)["R8"].result == "fail"


def test_r8_without_blocks_or_risk_is_not_applicable(registry, catalogue):
    r = run(TEXT, registry, catalogue)["R8"]
    assert r.result == "not_applicable" and "renderowaniu" in r.explanation
    r = run(f"{HEAD}. Reklama.", registry, catalogue, blocks=[block(HEAD, size=32)])["R8"]
    assert r.result == "not_applicable"
    assert "brak informacji o ryzyku" in r.explanation.lower()


@pytest.mark.parametrize("bad", ["min_font_px: 0", "min_font_px: -1", "min_font_px: x", "min_font_px: true"])
def test_r8_bad_min_font_px_fails_at_load(tmp_path, bad):
    text = CATALOGUE.read_text(encoding="utf-8")
    assert text.count("min_font_px: 12") == 1
    p = tmp_path / "m2.yaml"
    p.write_text(text.replace("min_font_px: 12", bad), encoding="utf-8")
    with pytest.raises(CatalogueError, match="R8 min_font_px"):
        Catalogue.load(p)


def test_r8_zero_px_warning_is_uncertain(registry, catalogue):
    assert run(TEXT, registry, catalogue, blocks=page(risk_mobile={"size": 0}))["R8"].result == "uncertain"


# ---- R13 dominance of past performance and the year-range detector ------------------------------

PAST = "Portfel 2021-2025: łączna stopa zwrotu 120%."
PP_DISCLAIMER = "Wyniki historyczne nie stanowią wiarygodnego wskaźnika przyszłych wyników."
PP_TEXT = f"Nagłówek kampanii. +120% w 5 lat! Bank Kwarcowy S.A. Reklama. {PAST} {PP_DISCLAIMER} {RISK}"


def pp_page(headline_size=56, mobile=True, headline="+120% w 5 lat!"):
    """A 32 px campaign heading on top, the headline under it, a 16 px past-performance paragraph, the warnings."""
    blocks = [block("Nagłówek kampanii", size=32, bbox=(0, 0, 800, 50)),
              block(headline, size=headline_size, bbox=(0, 70, 800, 60)),
              block(f"Bank Kwarcowy S.A. Reklama. {PAST}", size=16, bbox=(0, 140, 800, 40)),
              block(f"{PP_DISCLAIMER} {RISK}", size=14, bbox=(0, 200, 800, 40))]
    if mobile:
        blocks += [dict(b, viewport="mobile") for b in blocks]
    return blocks


def test_year_range_is_a_past_marker(registry, catalogue):
    r = run(f"{PAST} {PP_DISCLAIMER}", registry, catalogue)
    assert r["R14"].result == "pass"
    assert run("Prognoza na lata 2026-2030: 8% rocznie.", registry, catalogue)["R14"].result == "not_applicable"
    assert run("Portfel 2021-2027: łączna stopa zwrotu 120%.", registry, catalogue)["R14"].result == "not_applicable"


def test_r13_gold_headline_restating_a_past_return_fails(registry, catalogue):
    r = run_gold("m2-r13-past-performance-dominates", registry, catalogue)["R13"]
    assert r.result == "fail"
    assert r.evidence == "+120% w 5 lat!"
    assert r.evidence_locator.viewport == "desktop"
    assert "56 px" in r.explanation


def test_r13_gold_past_performance_in_body_text_passes(registry, catalogue):
    r = run_gold("m2-r12-past-performance-compliant", registry, catalogue)["R13"]
    assert r.result == "pass"
    assert r.evidence is not None and r.evidence.startswith("Stopa zwrotu w latach")


def test_r13_largest_past_performance_block_fails(registry, catalogue):
    text = f"Bank Kwarcowy S.A. Reklama. {PAST} {PP_DISCLAIMER} {RISK}"
    blocks = [block(f"Bank Kwarcowy S.A. Reklama. {PAST}", size=40, bbox=(0, 300, 800, 40)),
              block(f"{PP_DISCLAIMER} {RISK}", size=40, bbox=(0, 0, 800, 40))]
    r = run(text, registry, catalogue, blocks=blocks)["R13"]
    assert r.result == "fail"  # tied for the largest font
    assert r.evidence == PAST


def test_r13_first_block_above_dominant_size_fails(registry, catalogue):
    blocks = [block("+120% w 5 lat!", size=20, bbox=(0, 0, 800, 30)),
              block("Nagłówek kampanii", size=40, bbox=(0, 50, 800, 60)),
              block(f"Bank Kwarcowy S.A. Reklama. {PAST} {PP_DISCLAIMER} {RISK}", size=16, bbox=(0, 120, 800, 200))]
    text = f"+120% w 5 lat! Nagłówek kampanii. Bank Kwarcowy S.A. Reklama. {PAST} {PP_DISCLAIMER} {RISK}"
    assert run(text, registry, catalogue, blocks=blocks)["R13"].result == "fail"
    blocks[0]["font_size_px"] = 16  # first, but at the dominant size: not the most prominent element
    assert run(text, registry, catalogue, blocks=blocks)["R13"].result == "pass"


def test_r13_first_block_uses_position_not_list_order(registry, catalogue):
    blocks = [block("Nagłówek kampanii", size=40, bbox=(0, 0, 800, 60)),
              block("+120% w 5 lat!", size=20, bbox=(0, 600, 800, 30)),
              block(f"Bank Kwarcowy S.A. Reklama. {PAST} {PP_DISCLAIMER} {RISK}", size=16, bbox=(0, 120, 800, 200))]
    text = f"Nagłówek kampanii. +120% w 5 lat! Bank Kwarcowy S.A. Reklama. {PAST} {PP_DISCLAIMER} {RISK}"
    assert run(text, registry, catalogue, blocks=blocks)["R13"].result == "pass"
    blocks[1]["bbox"] = [0, -10, 800, 30]
    assert run(text, registry, catalogue, blocks=blocks)["R13"].result == "fail"


def test_r13_mobile_only_dominance_reports_mobile(registry, catalogue):
    blocks = pp_page(headline_size=12, mobile=False) + [dict(b, viewport="mobile") for b in pp_page(mobile=False)]
    r = run(PP_TEXT, registry, catalogue, blocks=blocks)["R13"]
    assert r.result == "fail"
    assert r.evidence_locator.viewport == "mobile"
    assert run(PP_TEXT, registry, catalogue, blocks=pp_page(headline_size=12))["R13"].result == "pass"


def test_r13_invisible_block_does_not_dominate(registry, catalogue):
    blocks = pp_page(mobile=False)
    assert run(PP_TEXT, registry, catalogue, blocks=blocks)["R13"].result == "fail"
    blocks[1]["visible"] = False
    assert run(PP_TEXT, registry, catalogue, blocks=blocks)["R13"].result == "pass"


def test_r13_a_figure_not_from_past_performance_is_not_linked(registry, catalogue):
    blocks = pp_page(mobile=False, headline="Prowizja 0% na start!")
    text = PP_TEXT.replace("+120% w 5 lat!", "Prowizja 0% na start!")
    assert run(text, registry, catalogue, blocks=blocks)["R13"].result == "pass"


def test_r13_without_past_performance_or_blocks_is_not_applicable(registry, catalogue):
    r = run(TEXT, registry, catalogue, blocks=page())["R13"]
    assert r.result == "not_applicable" and "wyników historycznych" in r.explanation
    r = run(PP_TEXT, registry, catalogue)["R13"]
    assert r.result == "not_applicable" and "renderowaniu" in r.explanation
    other = [block(HEAD, size=32), block(RISK)]
    r = run(PP_TEXT, registry, catalogue, blocks=other)["R13"]
    assert r.result == "not_applicable"


def test_r13_amount_only_past_performance_block_is_detected(registry, catalogue):
    claim = "Nasi klienci zarobili 5 000 zł w 2024 roku."
    text = f"{claim} Bank Kwarcowy S.A. Reklama. {PP_DISCLAIMER}"
    blocks = [block(claim, size=48, bbox=(0, 0, 800, 60)),
              block(f"Bank Kwarcowy S.A. Reklama. {PP_DISCLAIMER}", size=16, bbox=(0, 80, 800, 40))]
    r = run(text, registry, catalogue, blocks=blocks)["R13"]
    assert r.result == "fail"
    assert r.evidence == claim


# ---- detector year range: effect on R12a, R12b and R14 (wording not in the gold set) ---------------


def test_year_range_with_en_dash_triggers_the_past_performance_rules(registry, catalogue):
    text = ("Fundusz Akcji Rynków Wschodzących 2019–2023: średnio 6,4% rocznie. "
            "Wyniki historyczne nie są gwarancją przyszłych wyników.")
    r = run(text, registry, catalogue)
    assert r["R14"].result == "pass"
    assert r["R12a"].result != "not_applicable" and r["R12b"].result != "not_applicable"
    assert r["R12a"].evidence == "Fundusz Akcji Rynków Wschodzących 2019–2023: średnio 6,4% rocznie."


def test_year_range_reaching_past_the_fetch_year_is_not_past_performance(registry, catalogue):
    text = "Portfel modelowy 2023–2027: stopa zwrotu 7% rocznie."  # fetched in 2026: the range is not over yet
    r = run(text, registry, catalogue)
    assert r["R12a"].result == r["R12b"].result == r["R14"].result == "not_applicable"


@pytest.mark.parametrize("fee", ["po opłatach", "po wszystkich kosztach", "po prowizjach"])
def test_r12b_after_fees_in_polish_is_a_fee_statement(registry, catalogue, fee):
    text = f"Portfel w latach 2021-2025 zyskał 120% ({fee}, w PLN). {PP_DISCLAIMER}"
    assert run(text, registry, catalogue)["R12b"].result == "pass"


def test_r13_a_fee_figure_in_the_past_sentence_is_not_linked(registry, catalogue):
    past = "W 2025 r. fundusz zarobił 12%, a opłata za zarządzanie wyniosła 0%."
    text = f"Prowizja 0% na start! Bank Kwarcowy S.A. Reklama. {past} {PP_DISCLAIMER}"
    blocks = [block("Prowizja 0% na start!", size=48, bbox=(0, 0, 800, 60)),
              block(f"Bank Kwarcowy S.A. Reklama. {past} {PP_DISCLAIMER}", size=16, bbox=(0, 80, 800, 80))]
    assert run(text, registry, catalogue, blocks=blocks)["R13"].result == "pass"
    blocks[0]["text"] = "Zarobiliśmy 12%!"
    assert run(text.replace("Prowizja 0% na start!", "Zarobiliśmy 12%!"), registry, catalogue,
               blocks=blocks)["R13"].result == "fail"
