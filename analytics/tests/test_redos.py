"""Hostile-input regressions: the sentence splitter and the R3 patterns (PR #26 review, required item 4) and every
M1/M3 signal pattern (analytics-m1-m3 whole-branch security review) stay linear.

The fixed code takes a few milliseconds per case, the old one 4-130 s. The checks must hold on a loaded runner (the
full suite, CI, parallel sessions), so none compares a single wall-clock sample with a fixed limit: a growth check
compares the best of interleaved runs at n and k*n (load only ever adds time, and a spike hits one sample, not the
minimum) in CPU time, and an absolute budget counts CPU time too (`process_time`, which does not grow while the
process waits for a core).
"""

from __future__ import annotations

import math
import re
import time
from pathlib import Path

import pytest

from conftest import NOW, make_doc
from investwatch_analytics.config import SEED_REGISTRY, Settings
from investwatch_analytics.models import ScrapedDocument
from investwatch_analytics.pipeline import analyze
from investwatch_analytics.preprocessing import split_sentences
from investwatch_analytics.registry import Registry
from investwatch_analytics.rules.engine import Catalogue
from investwatch_analytics.rules.m1 import EVIDENCE_MAX


# A registered firm's own page: since analytics-m1-m3 only registered firms reach M2 (and so R3); the text is
# unchanged, so the sentence windows these tests pin stay the same.
FIRM_PAGE = "https://alfa-inwestycje.example.com/oferta"


def timed(fn) -> tuple[float, float]:
    """(wall, CPU) seconds of one call."""
    wall, cpu = time.perf_counter(), time.process_time()
    fn()
    return time.perf_counter() - wall, time.process_time() - cpu


def within(fn, budget: float, tries: int = 3, what: str = "") -> None:
    """`fn` costs under `budget` CPU seconds on its best of up to `tries` calls (stops at the first that fits, and
    does not retry a call far over budget: load does not triple CPU time)."""
    best = math.inf
    for _ in range(tries):
        best = min(best, timed(fn)[1])
        if best < budget or best > 3 * budget:
            break
    if best < budget:
        return
    pytest.fail(f"{best:.2f} CPU s, budget {budget} s {what}".rstrip())


def grows_at_most(small, big, *, factor: float, slack: float, budget: float | None = None, tries: int = 30,
                  patience_s: float = 2.0) -> None:
    """`big()` costs at most `factor * small() + slack` CPU seconds (and under `budget` CPU seconds), on the minimum of
    interleaved pairs of `timed` samples. CPU time, not wall-clock: a run of a few hundred milliseconds is descheduled
    on every try on a busy machine, so even its best wall-clock time is inflated (and inflated differently for the two
    sizes), while its CPU time does not count the wait. The ~16 ms resolution of `process_time` on Windows is inside
    `slack`, so millisecond runs pass, as they did by wall-clock. A linear pattern doubles from n to 2n and a quadratic
    one quadruples on every pair, and the running minimum of the smaller run only falls, so the retries do not let a
    quadratic one through. Stops at the first pair that holds (a quiet run measures once), else after `tries` pairs or
    `patience_s` seconds of retrying."""
    s_wall = s_cpu = b_wall = b_cpu = math.inf
    deadline = time.perf_counter() + patience_s
    for _ in range(tries):
        (sw, sc), (bw, bc) = small(), big()
        s_wall, s_cpu, b_wall, b_cpu = min(s_wall, sw), min(s_cpu, sc), min(b_wall, bw), min(b_cpu, bc)
        if b_cpu < factor * s_cpu + slack and (budget is None or b_cpu < budget):
            return
        if time.perf_counter() > deadline:
            break
    pytest.fail(f"CPU {s_cpu:.4f} -> {b_cpu:.4f} s (wall {s_wall:.4f} -> {b_wall:.4f} s): more than {factor}x + {slack} s"
                + (f", or big over {budget} CPU s" if budget is not None else ""))


@pytest.mark.parametrize(
    "text",
    [
        "." + " " * 50_000,
        "a." + " " * 100_000 + "x",  # #35 review 2: the `_BOUNDARY` shape Kacper timed (fixed on #26, 9bd27e8)
        ". " + " " * 40_000 + "abc",
        "S.A. Ab " * 6_000,  # abbreviation chain: every boundary is skipped, `start` never moves
        "ok. 1 " * 8_000,
        "\n" + " " * 50_000 + "x",
    ],
    ids=["dot-spaces", "dot-letter-spaces-100k", "dot-spaces-lowercase", "abbrev-chain", "abbrev-before-digit", "newline-spaces"],  # the last was already linear
)
def test_split_is_fast_on_hostile_input(text):
    within(lambda: split_sentences(text), 1.0)


# `digit-run`, `repeated-fee-stem` and `claim-warning-pairs` were quadratic before the fix; the others pin cases
# that were already linear, so they stay linear.
# Growth from half the input to the whole one, through the whole pipeline (fixed costs only make it look more linear).
@pytest.mark.parametrize(
    "prefix, unit, count",
    [("", "1", 50_000), ("", "1.2", 15_000), ("prowizja ", "9", 50_000), ("", "prowizj", 8_000),
     ("", "Zysk 5%. Ryzyko straty. ", 8_000)],
    ids=["digit-run", "dotted-digits", "fee-then-digits", "repeated-fee-stem", "claim-warning-pairs"],
)
def test_r3_patterns_are_fast_on_hostile_input(prefix, unit, count):
    registry, catalogue = Registry.from_csv(SEED_REGISTRY), Catalogue.load()
    docs = {n: ScrapedDocument.model_validate(make_doc(text="Reklama. " + prefix + unit * n, url=FIRM_PAGE))
            for n in (count // 2, count)}

    def run(n: int) -> tuple[float, float]:
        return timed(lambda: analyze(docs[n], registry=registry, catalogue=catalogue, now=NOW))

    grows_at_most(lambda: run(count // 2), lambda: run(count), factor=3.0, slack=0.05, budget=3.0)


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
    registry = Registry.from_csv(SEED_REGISTRY)
    doc = ScrapedDocument.model_validate(make_doc(text="Reklama. Zarabiaj 12,5 % rocznie z nami.", url=FIRM_PAGE))
    [f] = analyze(doc, registry=registry, catalogue=Catalogue.load(), now=NOW)
    [r3] = [r for r in f.rules if r.rule_id == "R3"]
    assert r3.result == "fail" and "12,5 %" in (r3.evidence or "")


def test_r3_claim_patterns_alone_are_linear_on_a_digit_run():
    """Each R3 claim and claim-exclude pattern on 20 000 digits: was ~25 s (quadratic), must stay under 2 s."""
    import re

    params = Catalogue.load().get("R3").params
    digits = "1" * 20_000
    for pattern in params["claim_patterns"] + params["claim_exclude_patterns"]:
        compiled = re.compile(pattern, re.IGNORECASE)
        within(lambda: list(compiled.finditer(digits)), 2.0, what=pattern)


def test_r3_coverage_unchanged_by_bisect():
    """Covered and uncovered claims around the +-2 sentence window, as before the bisect rewrite
    (old and new coverage logic agreed on 200 000 random claim/warning layouts)."""
    registry = Registry.from_csv(SEED_REGISTRY)

    def r3(text):
        [f] = analyze(ScrapedDocument.model_validate(make_doc(text=text, url=FIRM_PAGE)), registry=registry,
                      catalogue=Catalogue.load(), now=NOW)
        return next(r for r in f.rules if r.rule_id == "R3")

    assert r3("Reklama. Zysk 8% rocznie. A. Ryzyko utraty kapitału.").result == "pass"  # warning 2 after
    assert r3("Reklama. Ryzyko utraty kapitału. A. Zysk 8% rocznie.").result == "pass"  # warning 2 before
    far = r3("Reklama. Zysk 8% rocznie. A. B. Ryzyko utraty kapitału.")  # 3 sentences away
    assert far.result == "fail" and far.evidence == "Zysk 8% rocznie."
    two = r3("Reklama. Zysk 8% rocznie. Ryzyko utraty kapitału. A. B. C. D. Zarabiaj 9% rocznie.")
    assert two.result == "fail" and two.evidence == "Zarabiaj 9% rocznie."  # the second claim is uncovered


# ---- M1/M3 signal patterns (analytics-m1-m3) -------------------------------------------------------

SEED = Path(__file__).resolve().parents[1] / "registry" / "seed.csv"
FILLERS = ["1 ", " ", ".", "9", "@", ",", "1.", "1 zł ", "kod ", "nie udzielamy ", "akcja ", "utm_", "ref", "\t"]
SIZE = 20_000
#: Doubling the input may at most about double the time (a quadratic pattern quadruples it), and the larger run stays
#: under a generous absolute limit (#35 review 2).
BUDGET_S = 3.0


def grows_linearly(run, size: int) -> None:
    grows_at_most(lambda: run(size), lambda: run(2 * size), factor=3.0, slack=0.05, budget=BUDGET_S)


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
        grows_linearly(lambda n: timed(lambda: list(rx.finditer(filler * (n // len(filler)) + "x"))), SIZE)


@pytest.mark.parametrize("rule_id, module", [("R2", "M2"), ("S1.3", "M1")])
def test_negation_before_is_linear(rule_id, module):
    """R2/S1.3 look back at most 40 characters before each label; a run of negations and labels stays linear."""
    from investwatch_analytics.rules import engine
    from investwatch_analytics.preprocessing import preprocess
    from investwatch_analytics.rules.engine import Context

    cat = Catalogue.load() if module == "M2" else Catalogue.load_module("M1")
    rule = engine._RULES[rule_id](cat.get(rule_id))
    registry = Registry.from_csv(SEED)

    def run(n: int) -> tuple[float, float]:
        unit = "nie nie to nie jest reklama " if rule_id == "R2" else "nie nie to nie współpraca reklamowa "
        doc = ScrapedDocument.model_validate(make_doc(text=unit * (n // len(unit))))
        ctx = Context(doc=doc, pre=preprocess(doc.text), firm_match=None, registry=registry)
        return timed(lambda: rule.evaluate(ctx))

    grows_linearly(run, SIZE)


@pytest.mark.parametrize("href_body", ["ref" * 7_000, "utm_" * 5_000, "&utm_" * 4_000, "&ref=1" * 3_000, "?" * 20_000])
def test_s12_query_regexes_are_linear(href_body):
    from investwatch_analytics.rules import engine

    rule = engine._RULES["S1.2"](Catalogue.load_module("M1").get("S1.2"))
    referral, tracking = rule._query

    def run(n: int) -> tuple[float, float]:
        href = "https://x.example.com/?" + href_body[: n]
        return timed(lambda: (rule._query_part(href, referral), rule._query_part(href, tracking)))

    grows_linearly(run, SIZE)


@pytest.mark.parametrize("unit", ["współpraca ", "#reklama", "partner reklamowy ", "a" * 50])
def test_word_patterns_are_linear(unit):
    from investwatch_analytics.rules.m1 import word_patterns

    labels = word_patterns(Catalogue.load_module("M1").get("S1.3").params["labels"])
    grows_linearly(lambda n: timed(lambda: [list(p.finditer(unit * (n // len(unit)))) for p in labels]), SIZE)


@pytest.fixture(scope="module")
def registry() -> Registry:
    return Registry.from_csv(SEED)


def test_long_digit_run_through_the_pipeline(registry):
    doc = ScrapedDocument.model_validate(make_doc(source_kind="unknown", platform="web",
                                                  url="https://kursy.example.com/a", text="Kursy: " + "1 " * 20_000))
    within(lambda: analyze(doc, registry=registry, catalogue=Catalogue.load(), now=NOW), 5.0)


def test_long_href_is_fast(registry):
    href = "https://x.example.com/?" + "utm_" * 20_000
    doc = ScrapedDocument.model_validate(make_doc(source_kind="third_party", platform="instagram",
                                                  url="https://www.instagram.com/p/L1/", text="Alfa Inwestycje DM.",
                                                  links=[{"href": href}]))
    within(lambda: analyze(doc, registry=registry, catalogue=Catalogue.load(), now=NOW), 2.0)
    [f] = analyze(doc, registry=registry, catalogue=Catalogue.load(), now=NOW)
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


@pytest.mark.parametrize("unit", ["1,", "​", "x "], ids=["digit-commas", "zero-width", "letter-words"])
def test_megabyte_of_hostile_text_costs_no_more_than_the_scan_cap(unit):
    """1 MB through the pipeline: a generous absolute limit, and no more than about the cost of the 200 KB scan cap
    (without the cap it grows about 5x)."""
    from investwatch_analytics.pipeline import SCAN_MAX

    registry = Registry.from_csv(SEED_REGISTRY)

    def run(size: int) -> tuple[float, float]:
        doc = ScrapedDocument.model_validate(make_doc(source_kind="third_party", platform="web",
                                                      url="https://forum.example.com/t/1",
                                                      text="Wpis: " + unit * (size // len(unit))))
        return timed(lambda: analyze(doc, registry=registry, catalogue=Catalogue.load(), now=NOW))

    grows_at_most(lambda: run(SCAN_MAX), lambda: run(1_000_000), factor=2.0, slack=1.0, budget=20.0, tries=3)


def test_page_host_of_a_backslash_url_is_empty():
    from investwatch_analytics.modules.advertiser import page_host

    assert page_host(r"https://attacker.net\@alfa-inwestycje.example.com/") == ""


def test_expanding_ligatures_are_bounded_in_registry_lookups():
    """'ﬁ' folds to two characters under NFKC; R1's name lookup and the registry match read at most the 200 000-character
    prefix, so 2 MB of them costs about what the prefix costs (review-2 security pass). Preprocessing's own NFKC of the
    whole text is a separate follow-up."""
    registry = Registry.from_csv(SEED_REGISTRY)
    firm = next(f for f in registry.firms if f.name.startswith("Alfa"))

    def run(size: int) -> tuple[float, float]:
        text = "Alfa Inwestycje. " + "ﬁ" * size
        return timed(lambda: (registry.find_name(firm, text), registry.match(text, "https://x.example.com/")))

    grows_at_most(lambda: run(200_000), lambda: run(2_000_000), factor=3.0, slack=0.5, budget=10.0, tries=3)
