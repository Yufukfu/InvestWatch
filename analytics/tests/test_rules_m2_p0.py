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
