"""Hostile-input regressions (PR #26 review, required item 4): the sentence splitter and the R3 patterns stay linear.

Budgets are generous for CI runners; the fixed code takes a few milliseconds per case, the old one 4-130 s.
"""

from __future__ import annotations

import time

import pytest

from conftest import NOW, make_doc
from investwatch_analytics.config import Settings
from investwatch_analytics.models import ScrapedDocument
from investwatch_analytics.pipeline import analyze
from investwatch_analytics.preprocessing import split_sentences
from investwatch_analytics.registry import Registry
from investwatch_analytics.rules.engine import Catalogue


def elapsed(fn, *args) -> float:
    started = time.perf_counter()
    fn(*args)
    return time.perf_counter() - started


@pytest.mark.parametrize(
    "text",
    [
        "." + " " * 50_000,
        ". " + " " * 40_000 + "abc",
        "S.A. Ab " * 6_000,  # abbreviation chain: every boundary is skipped, `start` never moves
        "ok. 1 " * 8_000,
        "\n" + " " * 50_000 + "x",
    ],
    ids=["dot-spaces", "dot-spaces-lowercase", "abbrev-chain", "abbrev-before-digit", "newline-spaces"],
)
def test_split_is_fast_on_hostile_input(text):
    assert elapsed(split_sentences, text) < 1.0


@pytest.mark.parametrize("text", ["1" * 50_000, "1.2" * 15_000, "prowizja " + "9" * 50_000],
                         ids=["digit-run", "dotted-digits", "fee-then-digits"])
def test_r3_patterns_are_fast_on_hostile_input(text):
    registry = Registry.from_csv(Settings.from_env({}).registry_csv)
    doc = ScrapedDocument.model_validate(make_doc(text="Reklama. " + text))
    assert elapsed(lambda: analyze(doc, registry=registry, catalogue=Catalogue.load(), now=NOW)) < 3.0


def test_footnote_marker_with_spaces_still_starts_a_sentence():
    text = "Zysk 8% rocznie. *  Ryzyko utraty kapitału. (*)   Szczegóły w regulaminie."
    assert [s.text for s in split_sentences(text)] == [
        "Zysk 8% rocznie.", "*  Ryzyko utraty kapitału.", "(*)   Szczegóły w regulaminie."]


def test_abbreviation_window_keeps_legal_forms_and_years():
    # Same result as before the linear rewrite (old and new agreed on 20 009 texts, offsets included).
    text = "Alfa Inwestycje S.A. Zaprasza. Od 2024 r. Nowe konto. Cena ok. 15 zł. Wszystko jest ok. Dalej."
    assert [s.text for s in split_sentences(text)] == [
        "Alfa Inwestycje S.A. Zaprasza.", "Od 2024 r. Nowe konto.", "Cena ok. 15 zł.",
        "Wszystko jest ok.", "Dalej."]


def test_percent_claim_still_found():
    registry = Registry.from_csv(Settings.from_env({}).registry_csv)
    doc = ScrapedDocument.model_validate(make_doc(text="Reklama. Zarabiaj 12,5 % rocznie z nami."))
    [f] = analyze(doc, registry=registry, catalogue=Catalogue.load(), now=NOW)
    [r3] = [r for r in f.rules if r.rule_id == "R3"]
    assert r3.result == "fail" and "12,5 %" in (r3.evidence or "")
