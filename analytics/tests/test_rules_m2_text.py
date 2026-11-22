"""M2 text rules R10 and R9 (change analytics-m2-text-rules) and the per-sentence language guess.

Kept apart from the other M2 test files so the parallel visual-rules change does not collide here. Mock scenarios
read `contracts/mocks/documents.json` (never edited). The LLM is a fake judge only.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from conftest import make_doc
from investwatch_analytics.models import ScrapedDocument
from investwatch_analytics.preprocessing import guess_language, preprocess, sentence_language, split_sentences
from investwatch_analytics.registry import Registry
from investwatch_analytics.rules.engine import Catalogue, Context, run_rules

SEED = Path(__file__).resolve().parents[1] / "registry" / "seed.csv"
BANK_OK_ID = "5030107e"

EUROTRADE = (
    "Handluj CFD na indeksy z bonusem 500 zł na start! Nasi klienci zarobili średnio 34% w 2025 roku. "
    "W przyszłym roku spodziewamy się jeszcze lepszych wyników. Risk warning: CFDs are complex instruments "
    "and come with a high risk of losing money rapidly due to leverage."
)
EN_WARNING = (
    "Risk warning: CFDs are complex instruments and come with a high risk of losing money rapidly due to leverage."
)
PL_WARNING = (
    "Inwestowanie w instrumenty finansowe wiąże się z ryzykiem utraty części lub całości zainwestowanego kapitału."
)
NO_RISK = "brak informacji o ryzyku"


@pytest.fixture(scope="module")
def registry() -> Registry:
    return Registry.from_csv(SEED)


@pytest.fixture(scope="module")
def catalogue() -> Catalogue:
    return Catalogue.load()


def run(text: str, registry: Registry, catalogue: Catalogue, judge=None, **doc_fields) -> dict:
    doc = ScrapedDocument.model_validate(make_doc(text=text, **doc_fields))
    ctx = Context(doc=doc, pre=preprocess(text), firm_match=registry.match(text, doc.url), registry=registry)
    return {r.rule_id: r for r in run_rules(catalogue, ctx, judge, module="M2")}


def block(text: str, *, region: str | None = "main", viewport: str = "desktop", visible: bool = True) -> dict:
    return {"viewport": viewport, "text": text, "font_size_px": 16, "visible": visible, "region": region}


# ---- per-sentence language guess ----------------------------------------------------------------


def test_sentence_language_eurotrade():
    assert sentence_language("Nasi klienci zarobili średnio 34% w 2025 roku.") == "pl"
    assert sentence_language(EN_WARNING) == "en"


@pytest.mark.parametrize("text", ["Ryzyko!", "Reklama.", "", "   ", "CFD 1:30"])
def test_sentence_language_too_little_signal(text):
    assert sentence_language(text) is None


def test_sentence_language_tie_is_none():
    assert sentence_language("the and na w") is None  # 2 : 2


def test_sentence_language_counts_diacritic_words():
    assert sentence_language("Zażółć gęślą jaźń") == "pl"


def test_sentence_language_needs_two_points():
    assert sentence_language("Inwestuj z nami") == "pl"  # inwestuj, z
    assert sentence_language("risk money") == "en"
    assert sentence_language("money") is None


def test_sentences_and_offsets_unchanged():
    # Recorded on `main` before this change: the guess is additive.
    assert [(s.start, s.end) for s in split_sentences(EUROTRADE)] == [(0, 49), (50, 96), (97, 155), (156, 265)]
    assert preprocess(EUROTRADE).lang == guess_language(EUROTRADE) == "pl"


# ---- R10 language consistency -------------------------------------------------------------------


def test_r10_catalogue_entry(catalogue):
    spec = catalogue.get("R10")
    assert spec.implemented
    assert spec.severity == "low"
    assert spec.legal_basis == "art. 44 ust. 2 lit. f rozp. del. 2017/565"
    assert spec.llm is None  # rules-only


def test_r10_eurotrade_english_warning_fails(registry, catalogue):
    r = run(EUROTRADE, registry, catalogue)["R10"]
    assert r.result == "fail"
    assert r.evidence == EN_WARNING
    assert r.method == "rule"
    assert "en" in r.explanation and "pl" in r.explanation


def test_r10_bank_ok_passes(mock_documents, registry, catalogue):
    raw = next(d for d in mock_documents if d["id"].startswith(BANK_OK_ID))
    doc = ScrapedDocument.model_validate(raw)
    ctx = Context(doc=doc, pre=preprocess(doc.text), firm_match=registry.match(doc.text, doc.url), registry=registry)
    r = {x.rule_id: x for x in run_rules(catalogue, ctx)}["R10"]
    assert r.result == "pass"
    assert r.evidence == PL_WARNING


def test_r10_bilingual_warning_passes(registry, catalogue):
    text = f"Handluj kontraktami CFD na indeksy i waluty. {EN_WARNING} {PL_WARNING}"
    r = run(text, registry, catalogue)["R10"]
    assert r.result == "pass"
    assert r.evidence == PL_WARNING


def test_r10_no_warning_not_applicable(registry, catalogue):
    r = run("Otwórz konto maklerskie i inwestuj w akcje z rynku GPW.", registry, catalogue)["R10"]
    assert r.result == "not_applicable"
    assert NO_RISK in r.explanation.lower()


def test_r10_unknown_language_uncertain(registry, catalogue):
    r = run("Otwórz konto maklerskie i inwestuj w akcje z rynku GPW. Ryzyko!", registry, catalogue)["R10"]
    assert r.result == "uncertain"


def test_r10_unknown_warning_next_to_foreign_one_uncertain(registry, catalogue):
    text = f"Otwórz konto maklerskie i inwestuj w akcje z rynku GPW. Ryzyko! {EN_WARNING}"
    assert run(text, registry, catalogue)["R10"].result == "uncertain"


def test_r10_main_language_from_body_sentences(registry, catalogue):
    # English ad, English warning: consistent.
    text = f"Trade CFDs on indices and currencies with your account. {EN_WARNING}"
    assert run(text, registry, catalogue)["R10"].result == "pass"


def test_r10_warning_does_not_set_main_language(registry, catalogue):
    # The long English warning would outweigh the short Polish body if it counted.
    assert run(f"Otwórz konto i inwestuj. {EN_WARNING}", registry, catalogue)["R10"].result == "fail"


def test_r10_main_language_is_length_weighted(registry, catalogue):
    # Two short English sentences against one long Polish one: by length Polish is the main language.
    text = (
        "Trade with us and win the money you need. Join the app and get your bonus. Otwórz konto maklerskie i inwestuj w akcje, obligacje i fundusze ETF z rynku GPW "
        f"w jednej aplikacji na telefon. {EN_WARNING}"
    )
    assert run(text, registry, catalogue)["R10"].result == "fail"


def test_r10_english_legal_block_does_not_set_main_language(registry, catalogue):
    legal = (
        "Legal notice: this website is operated by the company and all of the information on this page is "
        "provided for the purposes of marketing only and is not an offer for you to buy or sell any of the "
        "products that are listed here."
    )
    headline = "Otwórz konto maklerskie i inwestuj w akcje z rynku GPW."
    text = f"{headline} {legal} {PL_WARNING}"
    blocks = [block(headline), block(legal, region="legal"), block(PL_WARNING, region="footer")]
    r = run(text, registry, catalogue, blocks=blocks)["R10"]
    assert r.result == "pass"
    assert r.evidence == PL_WARNING


def test_r10_main_language_from_blocks_not_sentences(registry, catalogue):
    # The visible body block is English; the long Polish text sits only in the footer: the Polish warning fails.
    headline = "Trade CFDs on indices and currencies with your account."
    footer = "Otwórz konto maklerskie i inwestuj w akcje, obligacje i fundusze ETF z rynku GPW w jednej aplikacji."
    text = f"{headline} {footer} {PL_WARNING}"
    blocks = [block(headline), block(footer, region="footer"), block(PL_WARNING)]
    r = run(text, registry, catalogue, blocks=blocks)["R10"]
    assert r.result == "fail"
    assert r.evidence == PL_WARNING


def test_r10_hidden_and_other_viewport_blocks_ignored(registry, catalogue):
    headline = "Otwórz konto maklerskie i inwestuj w akcje z rynku GPW."
    english = "Trade CFDs on indices and currencies with your account and win the money you need."
    text = f"{headline} {english} {EN_WARNING}"
    blocks = [
        block(headline),
        block(english, visible=False),
        block(english, viewport="mobile"),
        block(english, viewport="mobile"),
    ]
    assert run(text, registry, catalogue, blocks=blocks)["R10"].result == "fail"


def test_r10_first_viewport_when_no_desktop(registry, catalogue):
    headline = "Trade CFDs on indices and currencies with your account."
    text = f"{headline} Otwórz konto maklerskie i inwestuj w akcje z rynku GPW w aplikacji. {EN_WARNING}"
    blocks = [block(headline, viewport="mobile")]
    assert run(text, registry, catalogue, blocks=blocks)["R10"].result == "pass"


def test_r10_blocks_without_language_fall_back_to_sentences(registry, catalogue):
    text = f"Otwórz konto maklerskie i inwestuj w akcje z rynku GPW. {EN_WARNING}"
    blocks = [block("CFD 1:30"), block(EN_WARNING)]
    assert run(text, registry, catalogue, blocks=blocks)["R10"].result == "fail"


def test_r10_falls_back_to_document_guess(registry, catalogue):
    # Every non-warning sentence lacks signal: the document guess (Polish here) is the main language.
    text = f"Reklama. {PL_WARNING} {EN_WARNING}"
    r = run(text, registry, catalogue)["R10"]
    assert r.result == "pass"
    assert r.evidence == PL_WARNING
