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
    assert {"R5", "R7"} <= implemented


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
