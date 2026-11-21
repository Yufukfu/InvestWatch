"""gold-set-evaluation: "Gold-set file" (shape) and "Gold-set validation before analysis"."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest import make_doc
from investwatch_analytics.evaluation.gold import GoldError, load_gold, rule_status
from investwatch_analytics.evaluation.known_ids import KNOWN_IDS, known_ids

SECRET = "TAJNY-TEKST-DOKUMENTU"
# Loaded-catalogue view of a build with only M2 (the worker base): id -> implemented.
M2_ONLY = {"M2": {"R1": True, "R2": True, "R3": True, "R5": False}, "M1": None, "M3": None}


def line(id_: str = "g1", *, expect=None, document=None, **extra) -> dict:
    item = {
        "id": id_,
        "origin": "synthetic",
        "basis": "ZASÓB R3",
        "document": document or make_doc(text=f"Reklama. {SECRET} Zysk 10% rocznie."),
        "expect": expect if expect is not None else {"M2": {"label": "positive", "rules": {"R3": "fail"}}},
    }
    item.update(extra)
    return item


def write(tmp_path: Path, *items, raw: str | None = None) -> Path:
    path = tmp_path / "gold.jsonl"
    if raw is None:
        raw = "\n".join(json.dumps(i, ensure_ascii=False) for i in items) + ("\n" if items else "")
    path.write_text(raw, encoding="utf-8")
    return path


def problems(path: Path) -> list[str]:
    with pytest.raises(GoldError) as exc:
        load_gold(path, M2_ONLY)
    return exc.value.problems


# ---- shape ---------------------------------------------------------------------------------------


def test_valid_line_loads_with_document_and_expectations(tmp_path):
    items = load_gold(write(tmp_path, line(hard_case="warning 3 sentences after the claim")), M2_ONLY)
    assert len(items) == 1
    item = items[0]
    assert item.id == "g1" and item.line == 1 and item.origin == "synthetic"
    assert item.hard_case == "warning 3 sentences after the claim"
    assert item.document.url == "https://example.com/oferta"
    assert item.expect["M2"].label == "positive"
    assert item.expect["M2"].rules == {"R3": "fail"}


def test_one_document_labeled_for_two_modules(tmp_path):
    expect = {"M1": {"label": "positive", "rules": {"S1.2": "fail"}}, "M3": {"label": "positive", "rules": {}}}
    item = load_gold(write(tmp_path, line(expect=expect)), M2_ONLY)[0]
    assert set(item.expect) == {"M1", "M3"}


def test_rules_are_optional_and_partial(tmp_path):
    item = load_gold(write(tmp_path, line(expect={"M2": {"label": "negative"}})), M2_ONLY)[0]
    assert item.expect["M2"].rules == {}


def test_blank_lines_between_items_are_skipped(tmp_path):
    raw = json.dumps(line("a")) + "\n\n   \n" + json.dumps(line("b")) + "\n"
    items = load_gold(write(tmp_path, raw=raw), M2_ONLY)
    assert [(i.id, i.line) for i in items] == [("a", 1), ("b", 4)]


def test_uknf_sample_origin_loads_like_synthetic(tmp_path):
    item = load_gold(write(tmp_path, line(origin="uknf-sample")), M2_ONLY)[0]
    assert item.origin == "uknf-sample"


# ---- failure paths -------------------------------------------------------------------------------


@pytest.mark.parametrize("raw", ["", "\n\n  \n"])
def test_empty_gold_set(tmp_path, raw):
    assert problems(write(tmp_path, raw=raw)) == ["no labeled document"]


def test_missing_file(tmp_path):
    msgs = problems(tmp_path / "nope.jsonl")
    assert len(msgs) == 1 and "cannot read" in msgs[0]


def test_invalid_json_names_line(tmp_path):
    raw = "\n".join(json.dumps(line(f"g{i}")) for i in range(1, 7)) + "\n{" + SECRET + "\n"
    msgs = problems(write(tmp_path, raw=raw))
    assert len(msgs) == 1 and msgs[0].startswith("line 7: ") and "invalid JSON" in msgs[0]
    assert SECRET not in msgs[0]


def test_line_not_an_object(tmp_path):
    msgs = problems(write(tmp_path, raw='["a"]\n'))
    assert msgs == ["line 1: not a JSON object"]


def test_document_without_url_names_field_not_text(tmp_path):
    doc = make_doc(text=f"Reklama. {SECRET}")
    del doc["url"]
    msgs = problems(write(tmp_path, line("doc-no-url", document=doc)))
    assert len(msgs) == 1
    assert msgs[0].startswith("line 1 (doc-no-url): document.url: ")
    assert SECRET not in msgs[0]


def test_unknown_module(tmp_path):
    msgs = problems(write(tmp_path, line(expect={"M4": {"label": "positive"}})))
    assert msgs == ["line 1 (g1): expect.M4: unknown module (allowed: M1, M2, M3)"]


def test_empty_expect(tmp_path):
    assert problems(write(tmp_path, line(expect={}))) == ["line 1 (g1): expect: no module labeled"]


def test_bad_document_label(tmp_path):
    msgs = problems(write(tmp_path, line(expect={"M2": {"label": "maybe"}})))
    assert msgs == ["line 1 (g1): expect.M2.label: 'maybe' is not one of negative, positive"]


def test_bad_rule_label(tmp_path):
    msgs = problems(write(tmp_path, line(expect={"M2": {"label": "positive", "rules": {"R3": "failed"}}})))
    assert msgs == ["line 1 (g1): expect.M2.rules.R3: 'failed' is not one of fail, not_applicable, pass"]


@pytest.mark.parametrize(("module", "rule_id"), [("M2", "R19"), ("M1", "S1.9"), ("M2", "R3 ")])
def test_unknown_rule_id(tmp_path, module, rule_id):
    msgs = problems(write(tmp_path, line(expect={module: {"label": "positive", "rules": {rule_id: "fail"}}})))
    assert msgs == [f"line 1 (g1): expect.{module}.rules.{rule_id}: unknown rule id for {module}"]


def test_rule_id_of_another_module(tmp_path):
    msgs = problems(write(tmp_path, line(expect={"M1": {"label": "positive", "rules": {"R3": "fail"}}})))
    assert msgs == ["line 1 (g1): expect.M1.rules.R3: rule id of M2, not M1"]


def test_duplicate_id_names_both_lines(tmp_path):
    msgs = problems(write(tmp_path, line("m2-r3-window-edge"), line("ok"), line("m2-r3-window-edge")))
    assert msgs == ["line 3 (m2-r3-window-edge): id: duplicate of line 1"]


@pytest.mark.parametrize(("field", "value", "message"), [
    ("origin", "scraped", "origin: 'scraped' is not one of synthetic, uknf-sample"),
    ("basis", "", "basis: must be a non-empty string"),
    ("hard_case", 3, "hard_case: must be a string"),
    ("labels", {}, "labels: unknown field"),
])
def test_bad_item_fields(tmp_path, field, value, message):
    assert problems(write(tmp_path, line(**{field: value}))) == [f"line 1 (g1): {message}"]


def test_missing_id(tmp_path):
    item = line()
    del item["id"]
    assert problems(write(tmp_path, item)) == ["line 1: id: must be a non-empty string"]


def test_empty_id(tmp_path):
    assert problems(write(tmp_path, line(""))) == ["line 1: id: must be a non-empty string"]


def test_every_problem_is_reported_at_once(tmp_path):
    msgs = problems(write(tmp_path, line("a", origin="x"), line("b", expect={"M4": {"label": "positive"}})))
    assert [m.split(":")[0] for m in msgs] == ["line 1 (a)", "line 2 (b)"]


def test_unknown_module_field_in_expectation(tmp_path):
    msgs = problems(write(tmp_path, line(expect={"M2": {"label": "positive", "rule": {}}})))
    assert msgs == ["line 1 (g1): expect.M2.rule: unknown field"]


# ---- known ids and rule status ------------------------------------------------------------------


def test_label_for_not_implemented_rule_is_valid(tmp_path):
    load_gold(write(tmp_path, line(expect={"M2": {"label": "positive", "rules": {"R5": "fail"}}})), M2_ONLY)
    assert rule_status("M2", "R5", M2_ONLY) == "not_implemented"
    assert rule_status("M2", "R3", M2_ONLY) == "implemented"


def test_label_for_signal_not_in_build_is_valid(tmp_path):
    load_gold(write(tmp_path, line(expect={"M1": {"label": "positive", "rules": {"S1.2": "fail"}}})), M2_ONLY)
    assert rule_status("M1", "S1.2", M2_ONLY) == "not_in_build"
    assert rule_status("M2", "R14", M2_ONLY) == "not_in_build"


def test_static_known_ids_match_the_stage2_catalogues():
    assert KNOWN_IDS["M2"] == ("R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9", "R10", "R11", "R12a",
                               "R12b", "R13", "R14", "R15", "R16", "R17", "R18")
    assert KNOWN_IDS["M1"] == tuple(f"S1.{i}" for i in range(1, 8))
    assert KNOWN_IDS["M3"] == tuple(f"S3.{i}" for i in range(1, 9))


def test_loaded_catalogue_extends_known_ids():
    ids = known_ids({"M2": {"R1": True, "R20": False}, "M1": None, "M3": None})
    assert "R20" in ids["M2"] and "R18" in ids["M2"] and "S1.1" in ids["M1"]
