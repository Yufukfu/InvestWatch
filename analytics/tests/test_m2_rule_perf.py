"""Cheaper M2 rule passes on hostile input (#93 doubled `claim-warning-pairs` in test_redos): same results.

`blank_exclusions` skips the sequential exclusion subs when none occurs; the past-performance detector runs
once per document for R14, R12a and R12b; R11 blanks once for both its lists; R16 builds its list once.
"""

from __future__ import annotations

import random
import re

import pytest

from conftest import NOW, make_doc
from investwatch_analytics.config import SEED_REGISTRY
from investwatch_analytics.models import ScrapedDocument
from investwatch_analytics.pipeline import analyze
from investwatch_analytics.preprocessing import preprocess
from investwatch_analytics.registry import Registry
from investwatch_analytics.rules import m2
from investwatch_analytics.rules.engine import Catalogue, Context

FIRM = "https://alfa-inwestycje.example.com/oferta"


def sequential(text, exclude):
    for x in exclude:
        text = x.sub(" ", text)
    return text


@pytest.fixture(scope="module")
def catalogue():
    return Catalogue.load()


def catalogue_rules(catalogue):
    """Rule instances as `run_rules` builds them (one per spec)."""
    from investwatch_analytics.rules.engine import _RULES

    return [_RULES[spec.id](spec) for spec in catalogue.implemented if spec.id in _RULES]


def exclusion_lists(catalogue):
    lists = []
    for r in catalogue_rules(catalogue):
        for attr in ("_p", "_pp"):
            try:
                params = getattr(r, attr)
            except Exception:  # noqa: BLE001 - a rule without that property
                continue
            for key, value in params.items():
                if isinstance(value, list) and value and all(isinstance(x, re.Pattern) for x in value) \
                        and ("_x" in key or "exclude" in key):
                    lists.append(value)
    return lists


WORDS = ("zysk 12% rocznie prowizja 5% podatek Belki 19% najlepszy lepszy niż lokata źródło: Bloomberg w 2023 r. "
         "prognoza 2027 koszty opłata 1,5% USD stopa zwrotu wyniki historyczne ostrzeżenie ryzyko").split()


def test_blank_exclusions_equals_sequential_subs_for_every_rule_list(catalogue):
    lists = exclusion_lists(catalogue)
    assert len(lists) >= 5
    rnd = random.Random(3)
    texts = [" ".join(rnd.choice(WORDS) for _ in range(rnd.randint(1, 20))) for _ in range(400)]
    for exclude in lists:
        for t in texts:
            assert m2.blank_exclusions(t, exclude) == sequential(t, exclude)


def test_blank_exclusions_skips_subs_when_nothing_matches(monkeypatch):
    calls = []

    class Spy:
        def __init__(self, p):
            self._p = re.compile(p, re.IGNORECASE)
            self.pattern, self.flags = self._p.pattern, self._p.flags

        def sub(self, repl, text):
            calls.append(self.pattern)
            return self._p.sub(repl, text)

    exclude = [Spy("prowizj\\w*"), Spy("podat\\w*")]
    assert m2.blank_exclusions("Zysk 5%", exclude) == "Zysk 5%" and calls == []
    assert m2.blank_exclusions("prowizja 1%", exclude) == "  1%" and calls == ["prowizj\\w*", "podat\\w*"]


def test_a_later_exclusion_revealed_by_an_earlier_one_is_still_applied():
    # "ab" -> "a b" only after "X" is blanked; sequential order must stay.
    exclude = [re.compile("X", re.I), re.compile("a b", re.I)]
    assert m2.blank_exclusions("aXb", exclude) == sequential("aXb", exclude)


@pytest.mark.parametrize("patterns", [[r"(a)\1", "z"], [r"(?P<x>a)(?P=x)", "z"], [r"(?i)abc", "z"]],
                         ids=["backref", "named-backref", "inline-flag"])
def test_patterns_that_cannot_be_combined_fall_back(patterns):
    exclude = [re.compile(p) for p in patterns]
    assert m2._any_exclusion(exclude) is None
    for t in ["aa z", "abc", "xyz", "AAz"]:
        assert m2.blank_exclusions(t, exclude) == sequential(t, exclude)


def test_mixed_flags_fall_back():
    exclude = [re.compile("a", re.I), re.compile("b")]
    assert m2._any_exclusion(exclude) is None


def test_cache_is_bounded_and_checked_by_identity():
    for i in range(m2._ANY_EXCLUSION_MAX + 50):
        m2.blank_exclusions("x", [re.compile(f"q{i}")])
    assert len(m2._ANY_EXCLUSION) <= m2._ANY_EXCLUSION_MAX
    first, second = [re.compile("aa")], [re.compile("bb")]
    m2.blank_exclusions("aa", first)
    m2._ANY_EXCLUSION[id(second)] = (first, m2._any_exclusion(first))   # a stale entry under a reused id
    assert m2.blank_exclusions("bb", second) == " "


def ctx_for(text, registry):
    doc = ScrapedDocument.model_validate(make_doc(text=text, url=FIRM))
    return Context(doc=doc, pre=preprocess(doc.text), firm_match=None, registry=registry)


def test_past_performance_once_per_document_and_never_stale(catalogue):
    registry = Registry.from_csv(SEED_REGISTRY)
    rules = [r for r in catalogue_rules(catalogue) if r.rule_id in ("R14", "R12a", "R12b")]
    assert len(rules) == 3
    a = ctx_for("W 2023 r. fundusz zarobił 12%. Kup teraz.", registry)
    b = ctx_for("Kup teraz. Najlepsza oferta.", registry)
    expected_a = [s for s in a.pre.sentences if rules[0].is_past_performance(s.text, a.doc.fetched_at.year)]
    assert expected_a and all(r.past_performance(a) == expected_a for r in rules)
    assert all(r.past_performance(b) == [] for r in rules)          # a new document: recomputed
    assert all(r.past_performance(a) == expected_a for r in rules)


def test_past_performance_memo_is_shared(catalogue, monkeypatch):
    registry = Registry.from_csv(SEED_REGISTRY)
    rules = [r for r in catalogue_rules(catalogue) if r.rule_id in ("R14", "R12a", "R12b")]
    assert len({r._pp_key for r in rules}) == 1    # the YAML anchors make them one detector
    ctx = ctx_for(" ".join(["W 2023 r. zysk 12%."] * 20), registry)
    calls = []
    real = m2._PastPerformance.is_past_performance
    monkeypatch.setattr(m2._PastPerformance, "is_past_performance",
                        lambda self, s, y: calls.append(1) or real(self, s, y))
    m2._PP_MEMO.clear()
    for r in rules:
        r.past_performance(ctx)
    assert len(calls) == len(ctx.pre.sentences)


def test_memo_returns_a_copy(catalogue):
    registry = Registry.from_csv(SEED_REGISTRY)
    r = next(r for r in catalogue_rules(catalogue) if r.rule_id == "R14")
    ctx = ctx_for("W 2023 r. zysk 12%.", registry)
    first = r.past_performance(ctx)
    first.clear()
    assert r.past_performance(ctx)


def test_r16_list_is_the_old_concatenation(catalogue):
    r = next(r for r in catalogue_rules(catalogue) if r.rule_id == "R16")
    p = r._p
    assert r._tax_x_stripped == p["tax_x"] + p["individual"] + p["change"] + p["subject"]
    assert r._tax_x_stripped is r._tax_x_stripped


def test_r11_on_both_lists():
    registry, catalogue = Registry.from_csv(SEED_REGISTRY), Catalogue.load()
    doc = ScrapedDocument.model_validate(make_doc(
        text="Reklama. Nasz fundusz jest lepszy niż lokata bankowa o 3 pkt proc. Najlepszy fundusz na rynku.", url=FIRM))
    [f] = analyze(doc, registry=registry, catalogue=catalogue, now=NOW)
    r11 = next(r for r in f.rules if r.rule_id == "R11")
    assert r11.result in ("fail", "uncertain") and "lepszy niż lokata" in r11.evidence


def test_r16_strips_disclaimer_words_only_in_disclaimer_sentences():
    """`podatkowe` is a tax reference; the subject patterns blank it only inside a disclaimer sentence."""
    registry, catalogue = Registry.from_csv(SEED_REGISTRY), Catalogue.load()
    doc = ScrapedDocument.model_validate(make_doc(text="Reklama. Korzyści podatkowe dla oszczędzających.", url=FIRM))
    [f] = analyze(doc, registry=registry, catalogue=catalogue, now=NOW)
    r16 = next(r for r in f.rules if r.rule_id == "R16")
    assert r16.result != "not_applicable"


def test_conditional_group_reference_falls_back():
    exclude = [re.compile(r"(a)?(?(1)b|c)"), re.compile("z")]
    assert m2._any_exclusion(exclude) is None
    for t in ["ab", "c", "zz", "xyz"]:
        assert m2.blank_exclusions(t, exclude) == sequential(t, exclude)
