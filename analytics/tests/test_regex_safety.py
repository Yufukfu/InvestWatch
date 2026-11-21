"""ReDoS guard for catalogue patterns (analytics-m2-p1-rules design §8).

Catalogue patterns run on untrusted scraped text and Python `re` has no timeout, so the loader rejects a pattern
that nests an unbounded repetition inside another one, and a timing test searches every M2 pattern and every
module-level regex of `rules/m2.py` over adversarial input.
"""

from __future__ import annotations

import re
import time

import pytest

from investwatch_analytics.rules import engine, m2
from investwatch_analytics.rules.engine import Catalogue, CatalogueError

NESTED = [r"(\w+\s*)+niż", r"(?:a*)*", r"(.+)+", r"(?:x(?:\d+,)+y)+", r"(?:(?:\w+\s+){0,3})+", r"(?:a+?)+", r"(?:[+-9]+x)+"]
BOUNDED = [r"(?:\w+\s+){0,3}", r".{0,80}?", r"\bwynik\w*\s+(?:\w+\s+){0,2}nie\b", r"(?:ab|cd)+", r"\d+(?:[.,]\d+)?\s?%", r"[+-9]", r"[,-.]+", "[\x1c- ]"]


def write_catalogue(tmp_path, params: dict) -> object:
    import yaml

    path = tmp_path / "rules.yaml"
    entry = {"id": "R11", "name": "Porównania produktów", "severity": "medium", "implemented": False, "params": params}
    path.write_text(yaml.safe_dump({"rules": [entry]}, allow_unicode=True), encoding="utf-8")
    return path


@pytest.mark.parametrize("pattern", NESTED)
def test_nested_unbounded_repeat_is_rejected_in_patterns(tmp_path, pattern):
    path = write_catalogue(tmp_path, {"comparison_patterns": ["\\bok\\b", pattern]})
    with pytest.raises(CatalogueError, match=r"R11 comparison_patterns .*nested unbounded"):
        Catalogue.load(path)


@pytest.mark.parametrize("pattern", NESTED[:3])
def test_nested_unbounded_repeat_is_rejected_in_negation_before(tmp_path, pattern):
    path = write_catalogue(tmp_path, {"negation_before": pattern})
    with pytest.raises(CatalogueError, match=r"R11 negation_before .*nested unbounded"):
        Catalogue.load(path)


@pytest.mark.parametrize("pattern", BOUNDED)
def test_bounded_gaps_are_accepted(tmp_path, pattern):
    path = write_catalogue(tmp_path, {"comparison_patterns": [pattern], "negation_before": pattern})
    assert Catalogue.load(path).get("R11").params["comparison_patterns"] == [pattern]


def test_parser_shape():
    # A renamed private parser must fail loudly here, never make the lint pass everything silently.
    assert callable(engine._sre_parser.parse)
    assert engine.nested_unbounded_repeat(r"(a+)+")
    assert engine.nested_unbounded_repeat(r"x|(?=(?:b*c)*)")  # inside a branch and a lookahead
    assert not engine.nested_unbounded_repeat(r"(?:a+b){0,5}")


def test_shipped_catalogues_pass_the_lint():
    for module in ("M1", "M2", "M3"):
        Catalogue.load_module(module)


ADVERSARIAL = {
    "word-space": "a " * 10_000,
    "percent": "%" * 20_000,
    "niz": "niż " * 5_000,
    "one-word": "a" * 20_000,
    "digit-space": "1 " * 10_000,
    "digit-then-spaces": "1" + " " * 20_000,
}


def _m2_patterns() -> list[tuple[str, re.Pattern]]:
    out = []
    for spec in Catalogue.load().specs:
        for key, value in spec.params.items():
            if key.endswith("_patterns"):
                out += [(f"{spec.id}.{key}", re.compile(p, re.IGNORECASE)) for p in value]
            elif key == "negation_before":
                out.append((f"{spec.id}.{key}", re.compile(value, re.IGNORECASE)))
    out += [(f"m2.{name}", value) for name, value in vars(m2).items() if isinstance(value, re.Pattern)]
    return out


def _timed(pattern: re.Pattern, text: str) -> float:
    started = time.perf_counter()
    pattern.search(text)
    return time.perf_counter() - started


@pytest.mark.parametrize("kind", sorted(ADVERSARIAL))
def test_every_m2_pattern_is_fast_on_adversarial_text(kind):
    text = ADVERSARIAL[kind]
    slow = []
    for name, pattern in _m2_patterns():
        # Best of 3: a busy runner pauses a linear search now and then; real backtracking is slow every time.
        took = min(_timed(pattern, text) for _ in range(3))
        if took > 0.2:
            slow.append((name, pattern.pattern, round(took, 3)))
    assert not slow, slow
