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
