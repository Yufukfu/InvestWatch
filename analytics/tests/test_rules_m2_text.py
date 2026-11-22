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


# ---- R9 comprehensibility (LLM-first) -----------------------------------------------------------

import yaml  # noqa: E402

from investwatch_analytics.llm.judge import JudgeOutcome, LlmVerdict  # noqa: E402
from investwatch_analytics.rules.engine import DEFAULT_CATALOGUE, CatalogueError  # noqa: E402

JARGON = (
    "Ekspozycja na ryzyko bazowe instrumentu implikuje asymetryczny profil wypłaty, a zmienność implikowana i "
    "ryzyko kredytowe kontrahenta mogą skutkować deprecjacją wartości rynkowej poniżej poziomu partycypacji."
)
JARGON_AD = f"Reklama. Certyfikaty strukturyzowane na indeks WIG20 z ochroną kapitału na poziomie 90%. {JARGON}"
CFD_WARNING = (
    "Kontrakty CFD są złożonymi instrumentami i wiążą się z wysokim ryzykiem szybkiej utraty środków z powodu "
    "dźwigni finansowej."
)
LONG_WARNING = (
    "Inwestowanie w instrumenty finansowe wiąże się z ryzykiem utraty części lub całości zainwestowanego kapitału, "
    "a klient powinien przed podjęciem decyzji zapoznać się z dokumentem, który opisuje wszystkie koszty, opłaty "
    "i ryzyka związane z tym produktem oraz sposób ich naliczania w czasie."
)


class FakeJudge:
    """Answers with the given verdicts and records the checks it was asked."""

    model_name = "fake"

    def __init__(self, *verdicts: LlmVerdict):
        self.verdicts = {v.rule_id: v for v in verdicts}
        self.calls: list[dict] = []

    def judge(self, **kw) -> JudgeOutcome:
        self.calls.append(kw)
        return JudgeOutcome(verdicts=dict(self.verdicts), model="fake")

    def asked(self) -> set[str]:
        return {c.rule_id for call in self.calls for c in call["checks"]}


def load_with(tmp_path, rule_id: str, params: dict) -> Catalogue:
    data = yaml.safe_load(DEFAULT_CATALOGUE.read_text(encoding="utf-8"))
    entry = next(e for e in data["rules"] if e["id"] == rule_id)
    entry["params"] = {**(entry.get("params") or {}), **params}
    path = tmp_path / "rules.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return Catalogue.load(path)


def test_r9_catalogue_entry(catalogue):
    spec = catalogue.get("R9")
    assert spec.implemented
    assert spec.severity == "low"
    assert spec.legal_basis == "art. 44 ust. 2 lit. d rozp. del. 2017/565"
    assert spec.llm is not None and spec.llm["when"] == "uncertain"
    assert "Ocena: N/5" in spec.llm["question"]


def test_r9_jargon_warning_rules_only_uncertain(registry, catalogue):
    r = run(JARGON_AD, registry, catalogue)["R9"]
    assert r.result == "uncertain"
    assert r.evidence == JARGON
    assert r.method == "rule"
    assert "specjalistyczn" in r.explanation


@pytest.mark.parametrize("warning", [PL_WARNING, CFD_WARNING])
def test_r9_plain_warning_passes_and_is_not_deferred(registry, catalogue, warning):
    judge = FakeJudge(LlmVerdict("R9", "fail", warning, "Ocena: 1/5. Niezrozumiałe."))
    r = run(f"Reklama. Otwórz rachunek i inwestuj w akcje z GPW. {warning}", registry, catalogue, judge)["R9"]
    assert r.result == "pass"
    assert r.evidence == warning
    assert "R9" not in judge.asked()


def test_r9_evidence_is_the_warning_with_most_jargon(registry, catalogue):
    r = run(f"Reklama. {PL_WARNING} {JARGON}", registry, catalogue)["R9"]
    assert r.result == "uncertain"
    assert r.evidence == JARGON


def test_r9_long_warning_uncertain(registry, catalogue):
    assert run(f"Reklama. {LONG_WARNING}", registry, catalogue)["R9"].result == "uncertain"


def test_r9_one_jargon_word_in_a_short_warning_uncertain(registry, catalogue):
    # One hit (under min_jargon_hits), but a high share: 1 of 5 words.
    text = "Reklama. Otwórz rachunek i inwestuj w akcje z GPW. Ryzyko kontrahenta oznacza możliwą stratę."
    assert run(text, registry, catalogue)["R9"].result == "uncertain"


def test_r9_two_jargon_hits_with_a_low_share_uncertain(registry, catalogue):
    # Two hits over ~50 words (share under 5%, average under 30 words): the hit count alone raises it.
    a = ("Inwestowanie w instrumenty finansowe wiąże się z ryzykiem utraty części kapitału, także z powodu "
         "zmian ceny, kursu waluty lub problemów finansowych naszego kontrahenta w czasie trwania umowy.")
    b = ("Wartość inwestycji może spaść poniżej kwoty wpłaconej przez klienta, bo zależy od zmienności cen na "
         "rynku, a hedging nie chroni w pełni przed ryzykiem straty części pieniędzy.")
    assert run(f"Reklama. {a} {b}", registry, catalogue)["R9"].result == "uncertain"


def test_r9_no_warning_not_applicable(registry, catalogue):
    r = run("Otwórz konto maklerskie i inwestuj w akcje z rynku GPW.", registry, catalogue)["R9"]
    assert r.result == "not_applicable"
    assert NO_RISK in r.explanation.lower()


def test_r9_deferred_only_when_uncertain(registry, catalogue):
    judge = FakeJudge()
    run(JARGON_AD, registry, catalogue, judge)
    assert "R9" in judge.asked()


def test_r9_model_low_rating_fails(registry, catalogue):
    judge = FakeJudge(LlmVerdict("R9", "fail", JARGON, "Ocena: 1/5. Żargon specjalistyczny."))
    r = run(JARGON_AD, registry, catalogue, judge)["R9"]
    assert r.result == "fail"
    assert r.evidence == JARGON
    assert r.method == "hybrid"


def test_r9_model_rating_two_is_the_boundary(registry, catalogue):
    judge = FakeJudge(LlmVerdict("R9", "fail", JARGON, "Ocena: 2/5. Trudne."))
    assert run(JARGON_AD, registry, catalogue, judge)["R9"].result == "fail"


@pytest.mark.parametrize("explanation", ["Ocena: 3/5. Średnio.", "Niezrozumiałe dla klienta.", "Ocena: 7/5.", "Ocena: 1/3."])
def test_r9_model_fail_without_a_low_rating_uncertain(registry, catalogue, explanation):
    judge = FakeJudge(LlmVerdict("R9", "fail", JARGON, explanation))
    r = run(JARGON_AD, registry, catalogue, judge)["R9"]
    assert r.result == "uncertain"


def test_r9_model_pass_needs_a_high_rating(registry, catalogue):
    high = FakeJudge(LlmVerdict("R9", "pass", JARGON, "Ocena: 4/5. Zrozumiałe."))
    assert run(JARGON_AD, registry, catalogue, high)["R9"].result == "pass"
    mid = FakeJudge(LlmVerdict("R9", "pass", JARGON, "Ocena: 3/5. Średnio."))
    assert run(JARGON_AD, registry, catalogue, mid)["R9"].result == "uncertain"


def test_r9_model_quote_not_in_document_uncertain(registry, catalogue):
    judge = FakeJudge(LlmVerdict("R9", "fail", "Zdanie, którego nie ma w tekście.", "Ocena: 1/5."))
    r = run(JARGON_AD, registry, catalogue, judge)["R9"]
    assert r.result == "uncertain"
    assert r.evidence is None


def test_other_rules_keep_their_llm_verdict(registry, catalogue):
    # The hook narrows only R9: R17's fail without a rating still stands.
    text = "Jesteśmy nadzorowani przez KNF."
    judge = FakeJudge(LlmVerdict("R17", "fail", text, "Sugeruje aprobatę nadzoru."))
    r = run(text, registry, catalogue, judge)["R17"]
    assert "R17" in judge.asked()
    assert r.result == "fail"


@pytest.mark.parametrize("params", [
    {"max_avg_sentence_words": 0}, {"max_avg_sentence_words": "dużo"}, {"max_avg_sentence_words": True},
    {"max_jargon_share": 0}, {"max_jargon_share": 1.5}, {"min_jargon_hits": 0}, {"min_jargon_hits": 1.5},
    {"jargon_patterns": ["("]},
])
def test_r9_bad_params_rejected(tmp_path, params):
    with pytest.raises(CatalogueError, match="R9"):
        load_with(tmp_path, "R9", params)


# ---- scoring: a rules-only R9 uncertain carries no evidence (Damian, change analytics-m2-text-rules) -------

from investwatch_analytics.modules.m2 import score  # noqa: E402


def results(text: str, registry, catalogue, judge=None) -> list:
    return list(run(text, registry, catalogue, judge).values())


def test_r9_declares_llm_only_uncertain(catalogue):
    assert catalogue.get("R9").llm_only_uncertain is True
    assert [s.id for s in catalogue.specs if s.llm_only_uncertain] == ["R9"]


def test_rules_only_r9_uncertain_does_not_change_the_score(registry, catalogue):
    rules = results(JARGON_AD, registry, catalogue)
    r9 = next(r for r in rules if r.rule_id == "R9")
    assert r9.result == "uncertain" and r9.method == "rule"
    without_r9 = [r for r in rules if r.rule_id != "R9"]
    assert score(rules, catalogue) == score(without_r9, catalogue)
    assert score(rules) != score(without_r9)  # without the catalogue every uncertain counts, as before


def test_llm_r9_fail_raises_the_score(registry, catalogue):
    judge = FakeJudge(LlmVerdict("R9", "fail", JARGON, "Ocena: 1/5. Żargon."))
    rules = results(JARGON_AD, registry, catalogue, judge)
    assert next(r for r in rules if r.rule_id == "R9").result == "fail"
    without_r9 = [r for r in rules if r.rule_id != "R9"]
    assert score(rules, catalogue) == score(rules) > score(without_r9, catalogue)


def test_llm_r9_uncertain_still_counts(registry, catalogue):
    judge = FakeJudge(LlmVerdict("R9", "fail", JARGON, "Ocena: 3/5. Średnio."))
    rules = results(JARGON_AD, registry, catalogue, judge)
    r9 = next(r for r in rules if r.rule_id == "R9")
    assert r9.result == "uncertain" and r9.method == "hybrid"
    as_pass = [r.model_copy(update={"result": "pass"}) if r.rule_id == "R9" else r for r in rules]
    assert score(rules, catalogue) == score(rules) > score(as_pass, catalogue)


def test_rules_only_r9_pass_is_scored(registry, catalogue):
    rules = results(f"Reklama. Otwórz rachunek i inwestuj w akcje z GPW. {PL_WARNING}", registry, catalogue)
    assert next(r for r in rules if r.rule_id == "R9").result == "pass"
    assert score(rules, catalogue) == score(rules)


def test_other_rules_uncertain_still_counts(registry, catalogue):
    # R2's rules-only uncertain (a label only mid-text) is unaffected by the flag.
    filler = " ".join(f"Zdanie numer {n} o ofercie." for n in range(6))
    rules = results(f"{filler} To jest reklama. {filler}", registry, catalogue)
    assert next(r for r in rules if r.rule_id == "R2").result == "uncertain"
    as_pass = [r.model_copy(update={"result": "pass"}) if r.rule_id == "R2" else r for r in rules]
    assert score(rules, catalogue) == score(rules) > score(as_pass, catalogue)


@pytest.mark.parametrize("value", ["yes", 1, None])
def test_llm_only_uncertain_must_be_a_boolean(tmp_path, value):
    data = yaml.safe_load(DEFAULT_CATALOGUE.read_text(encoding="utf-8"))
    next(e for e in data["rules"] if e["id"] == "R9")["llm_only_uncertain"] = value
    path = tmp_path / "rules.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    with pytest.raises(CatalogueError, match="R9"):
        Catalogue.load(path)
