"""gold-set-evaluation on the committed gold set: coverage, ZASÓB pairs, fictional names, FP/FN moving."""

from __future__ import annotations

import csv
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pytest

from investwatch_analytics.evaluation.gold import load_gold
from investwatch_analytics.evaluation.known_ids import KNOWN_IDS
from investwatch_analytics.evaluation.runner import DEFAULT_GOLD, DEFAULT_REGISTRY, EVAL_DIR, evaluate, load_build
from investwatch_analytics.registry import Registry

RUNTIME_REGISTRY = Path(__file__).resolve().parents[1] / "registry"
README = EVAL_DIR / "README.md"
ZASOB_RULES = KNOWN_IDS["M2"]  # R1-R18 with R12a and R12b, as listed in the ZASÓB table
MIN_DOCS = {"M1": 15, "M2": 20, "M3": 15}
DEFAULT = {"M1": 0.6, "M2": 0.5, "M3": 0.7}


@pytest.fixture(scope="module")
def build():
    return load_build()


@pytest.fixture(scope="module")
def items(build):
    return load_gold(DEFAULT_GOLD, build.catalogues)


@pytest.fixture(scope="module")
def report(items, build):
    return evaluate(items, registry=Registry.from_csv(DEFAULT_REGISTRY), build=build,
                    now=datetime(2026, 11, 21, tzinfo=timezone.utc), gold_sha256="0" * 64)


def labels(items, module):
    out: dict[str, Counter] = {}
    for i in items:
        if module in i.expect:
            for rule_id, label in i.expect[module].rules.items():
                out.setdefault(rule_id, Counter())[label] += 1
    return out


#: Signals the gold set does not need a `fail` for: S3.7 (KNF warnings list) needs a warnings list to check against.
NO_PAIR_NEEDED = {"S3.7"}


@pytest.mark.parametrize("module", ["M1", "M2", "M3"])
def test_coverage_per_module(items, build, module):
    labeled = [i for i in items if module in i.expect]
    positives = sum(i.expect[module].positive for i in labeled)
    assert len(labeled) >= MIN_DOCS[module]
    assert positives >= 5 and len(labeled) - positives >= 5
    counts = labels(items, module)
    implemented = [r for r, on in (build.catalogues.get(module) or {}).items() if on]
    # M1/M3: every known signal, so the labels are ready before the stage-2 catalogues are in this build.
    wanted = implemented if module == "M2" else sorted(set(implemented) | set(KNOWN_IDS[module]) - NO_PAIR_NEEDED)
    for rule_id in wanted:
        assert counts.get(rule_id, Counter())["fail"] >= 1, f"{module} {rule_id} has no fail label"
        assert counts.get(rule_id, Counter())["pass"] >= 1, f"{module} {rule_id} has no pass label"


@pytest.mark.parametrize("rule_id", ZASOB_RULES)
def test_every_zasob_rule_has_a_pair(items, rule_id):
    counts = labels(items, "M2").get(rule_id, Counter())
    assert counts["fail"] >= 1 and counts["pass"] >= 1, f"{rule_id}: {dict(counts)}"


def _names(path: Path) -> set[str]:
    out = set()
    with open(path, encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            for value in [row["name"], *(row.get("aliases") or "").split("|"),
                          *(row.get("website_domains") or "").split("|")]:
                if value.strip():
                    out.add(value.strip().lower())
    return out


def test_eval_registry_shares_no_firm_with_the_runtime_registry():
    runtime = set().union(*(_names(p) for p in RUNTIME_REGISTRY.glob("*.csv")))
    assert not _names(DEFAULT_REGISTRY) & runtime


def test_every_author_handle_is_a_listed_fictional_handle(items):
    listed = set(re.findall(r"^- `(@[\w.]+)`", README.read_text(encoding="utf-8"), re.MULTILINE))
    assert listed, "the README lists no fictional handles"
    used = {i.document.author.handle for i in items if i.document.author and i.document.author.handle}
    assert used <= listed, sorted(used - listed)


def test_phone_numbers_are_fictional(items):
    for i in items:
        for number in re.findall(r"\+48[\d ]{9,}", i.document.text):
            assert number.replace(" ", "").startswith("+48000"), (i.id, "real-looking phone number")


def test_every_line_names_its_basis_and_is_synthetic_or_uknf(items):
    assert all(i.basis.strip() for i in items)
    assert {i.origin for i in items} <= {"synthetic", "uknf-sample", "zasob-example"}


ZASOB_QUOTE = "w pełni bezpieczna – spełniamy rygorystyczne wymogi nadzorcze KNF"


def test_zasob_examples_quote_zasob(items):
    examples = [i for i in items if i.origin == "zasob-example"]
    assert examples, "no line uses a phrasing quoted in ZASÓB"
    assert any(ZASOB_QUOTE in i.document.text for i in examples)
    assert all(i.basis.startswith("ZASÓB") for i in examples)


def test_hard_cases_are_about_a_third(items):
    per_module = Counter(m for i in items for m in i.expect)
    hard = Counter(m for i in items if i.hard_case for m in i.expect)
    for module, n in per_module.items():
        assert hard[module] >= n // 4, f"{module}: {hard[module]} hard cases of {n}"


@pytest.mark.parametrize("module", ["M1", "M2", "M3"])
def test_thresholds_move_fp_and_fn(report, module):
    entry = report["modules"].get(module)
    if entry is None or entry["status"] != "evaluated":
        pytest.skip(f"{module} is not in this build or not labeled yet")
    at = {p["threshold"]: p for p in entry["points"]}
    here = at[DEFAULT[module]]
    around = [at[t] for t in (round(DEFAULT[module] - 0.2, 2), round(DEFAULT[module] + 0.2, 2)) if t in at]
    assert any((p["fp"], p["fn"]) != (here["fp"], here["fn"]) for p in around)


def test_rules_only_run_has_no_analysis_errors(report):
    assert report["run"]["analysis_errors"] == []
