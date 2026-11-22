"""Preprocessing normalizes once (change analytics-post-integration-fixes, group 3): the same result as deriving each
field separately, one NFKC pass, and linear growth on a large ligature text."""

from __future__ import annotations

import random
import time
import unicodedata

import pytest

from investwatch_analytics import preprocessing
from investwatch_analytics.preprocessing import (
    guess_language, normalize, preprocess, split_sentences,
)

#: Compatibility characters NFKC rewrites (ligature, fullwidth, NBSP, superscript, ellipsis), Polish letters in
#: composed and decomposed form, CR/LF and sentence punctuation, so random texts exercise every derived field.
ALPHABET = list("abcdefghij XYZ ąęłśż.!?…") + ["ﬁ", "ﬂ", "Ａ", "ｚ", " ", "²", "é", "\r\n", "\n\n", "  ",
                                                "\t", "S.A. ", "ok. 15", "Ryzyko. ", "„Zysk” "]


def field_by_field(text: str) -> tuple:
    return (normalize(text), guess_language(text), split_sentences(text))


def fields(text: str) -> tuple:
    p = preprocess(text)
    return (p.normalized, p.lang, p.sentences)


def random_text(rng: random.Random) -> str:
    return "".join(rng.choice(ALPHABET) for _ in range(rng.randint(0, 400)))


def test_same_result_on_mocks(mock_documents):
    for d in mock_documents:
        assert fields(d["text"]) == field_by_field(d["text"]), d["id"]


def test_same_result_on_random_texts():
    rng = random.Random(20261122)
    for _ in range(200):
        text = random_text(rng)
        assert fields(text) == field_by_field(text), repr(text)


@pytest.mark.parametrize("text", ["", "   ", "\r\n", "ﬁ" * 50, "Ｒｅｋｌａｍａ. Ryzyko straty. Zysk 15%."])
def test_same_result_on_edge_texts(text):
    assert fields(text) == field_by_field(text)
    p = preprocess(text)
    assert all(text[s.start:s.end] == s.text for s in p.sentences)


def test_one_nfkc_pass(monkeypatch):
    calls = []
    real = unicodedata.normalize

    def counting(form, value):
        calls.append(form)
        return real(form, value)

    monkeypatch.setattr(preprocessing.unicodedata, "normalize", counting)
    preprocess("Reklama ﬁnansowa. Ryzyko straty kapitału.")
    assert calls == ["NFKC"]


def _best_of(text: str, runs: int = 3) -> float:
    best = float("inf")
    for _ in range(runs):
        t = time.perf_counter()
        preprocess(text)
        best = min(best, time.perf_counter() - t)
    return best


def test_large_ligature_text_grows_linearly():
    """A ratio, never wall-clock: 4x the input must cost far less than the 16x of quadratic growth."""
    small, large = _best_of("ﬁ" * 100_000), _best_of("ﬁ" * 400_000)
    assert large / small < 8, (small, large)
