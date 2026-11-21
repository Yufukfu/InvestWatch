"""Scraped text is attacker-controlled: no M1/M3 pattern may be super-linear (whole-branch security review)."""

from __future__ import annotations

import re
import time
from pathlib import Path

import pytest

from conftest import NOW, make_doc
from investwatch_analytics.models import ScrapedDocument
from investwatch_analytics.pipeline import analyze
from investwatch_analytics.registry import Registry
from investwatch_analytics.rules.engine import Catalogue
from investwatch_analytics.rules.m1 import EVIDENCE_MAX

SEED = Path(__file__).resolve().parents[1] / "registry" / "seed.csv"
FILLERS = ["1 ", " ", ".", "9", "@", ",", "1.", "1 zł ", "kod ", "nie udzielamy ", "akcja ", "utm_", "ref", "\t"]
SIZE = 40_000
BUDGET_S = 0.5  # a quadratic pattern needs minutes at this size; a linear one well under a tenth of a second


def _patterns():
    for module in ("M1", "M3"):
        for spec in Catalogue.load_module(module).specs:
            for key, value in spec.params.items():
                if key.endswith("_patterns"):
                    for pat in value:
                        yield pytest.param(pat, id=f"{spec.id}:{key}:{pat[:24]}")


@pytest.mark.parametrize("pattern", list(_patterns()))
def test_catalogue_pattern_is_linear_on_adversarial_runs(pattern):
    rx = re.compile(pattern, re.IGNORECASE)
    for filler in FILLERS:
        text = filler * (SIZE // len(filler)) + "x"
        start = time.perf_counter()
        list(rx.finditer(text))
        assert time.perf_counter() - start < BUDGET_S, (pattern, filler)


@pytest.fixture(scope="module")
def registry() -> Registry:
    return Registry.from_csv(SEED)


def test_long_digit_run_through_the_pipeline(registry):
    doc = ScrapedDocument.model_validate(make_doc(source_kind="unknown", platform="web",
                                                  url="https://kursy.example.com/a", text="Kursy: " + "1 " * 20_000))
    start = time.perf_counter()
    analyze(doc, registry=registry, catalogue=Catalogue.load(), now=NOW)
    assert time.perf_counter() - start < 5


def test_long_href_is_fast(registry):
    href = "https://x.example.com/?" + "utm_" * 20_000
    doc = ScrapedDocument.model_validate(make_doc(source_kind="third_party", platform="instagram",
                                                  url="https://www.instagram.com/p/L1/", text="Alfa Inwestycje DM.",
                                                  links=[{"href": href}]))
    start = time.perf_counter()
    [f] = analyze(doc, registry=registry, catalogue=Catalogue.load(), now=NOW)
    assert time.perf_counter() - start < 2
    assert {r.rule_id: r.result for r in f.rules}["S1.2"] == "pass"


def test_evidence_is_capped(registry):
    sentence = "Kupuj akcje " + "bardzo " * 20_000 + "teraz."
    doc = ScrapedDocument.model_validate(make_doc(source_kind="unknown", platform="web",
                                                  url="https://sygnaly.example.com/", text=sentence,
                                                  author={"handle": "@" + "h" * 5000}))
    [f] = analyze(doc, registry=registry, catalogue=Catalogue.load(), now=NOW)
    rules = {r.rule_id: r for r in f.rules}
    assert rules["S3.4"].result == "uncertain" and len(rules["S3.4"].evidence) == EVIDENCE_MAX
    assert rules["S3.4"].evidence in doc.text
    assert len(rules["S3.1"].evidence) == EVIDENCE_MAX and rules["S3.1"].evidence in doc.author.handle
