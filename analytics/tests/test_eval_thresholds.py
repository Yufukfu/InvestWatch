"""gold-set-evaluation: "Recommended threshold" and "Default thresholds from the evaluation" (ADR 0316)."""

from __future__ import annotations

import ast
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from investwatch_analytics import events
from investwatch_analytics.evaluation import __main__ as cli
from investwatch_analytics.evaluation.gold import load_gold
from investwatch_analytics.evaluation.metrics import GRID, recommended_threshold
from investwatch_analytics.evaluation.runner import (
    DEFAULT_GOLD,
    DEFAULT_REGISTRY,
    THRESHOLDS_FILE,
    evaluate,
    load_build,
    write_thresholds,
)
from investwatch_analytics.registry import Registry

API_THRESHOLDS = Path(__file__).resolve().parents[2] / "api" / "src" / "investwatch_api" / "thresholds.py"


def points(f1_by_threshold: dict[float, float]) -> list[dict]:
    return [{"threshold": t, "f1": f1_by_threshold.get(t, 0.0)} for t in GRID]


def test_best_f1_wins():
    assert recommended_threshold(points({0.25: 0.70, 0.3: 0.67, 0.05: 0.6})) == 0.25


def test_tie_goes_to_the_higher_threshold():
    assert recommended_threshold(points({t: 0.889 for t in (0.4, 0.45, 0.5, 0.55, 0.6, 0.65)})) == 0.65


def test_nothing_found_has_no_recommendation():
    assert recommended_threshold(points({})) is None


def test_write_thresholds_keeps_modules_without_a_recommendation(tmp_path):
    path = tmp_path / "thresholds.json"
    path.write_text('{"M1": 0.6, "M2": 0.5, "M3": 0.7}\n', encoding="utf-8")
    report = {"modules": {"M1": {"status": "evaluated", "recommended_threshold": 0.65},
                          "M2": {"status": "evaluated", "recommended_threshold": None},
                          "M3": {"status": "not_run", "points": []}}}
    assert write_thresholds(path, report) == {"M1": 0.65, "M2": 0.5, "M3": 0.7}
    assert json.loads(path.read_text(encoding="utf-8")) == {"M1": 0.65, "M2": 0.5, "M3": 0.7}
    assert path.read_text(encoding="utf-8").endswith("\n")


def test_write_thresholds_without_a_previous_file(tmp_path):
    path = tmp_path / "thresholds.json"
    report = {"modules": {"M2": {"status": "evaluated", "recommended_threshold": 0.25}}}
    with pytest.raises(ValueError):
        write_thresholds(path, report)  # M1/M3 would have no value at all


def test_cli_write_thresholds(tmp_path, capsys, monkeypatch):
    path = tmp_path / "thresholds.json"
    path.write_text('{"M1": 0.6, "M2": 0.5, "M3": 0.7}\n', encoding="utf-8")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    code = cli.main(["--write-thresholds", str(path)])
    report = json.loads(capsys.readouterr().out)
    assert code in (0, 1)
    written = json.loads(path.read_text(encoding="utf-8"))
    for module, entry in report["modules"].items():
        if entry.get("recommended_threshold") is not None:
            assert written[module] == entry["recommended_threshold"]


@pytest.fixture(scope="module")
def fresh_run():
    build = load_build()
    items = load_gold(DEFAULT_GOLD, build.catalogues)
    return evaluate(items, registry=Registry.from_csv(DEFAULT_REGISTRY), build=build,
                    now=datetime(2026, 11, 22, tzinfo=timezone.utc), gold_sha256="0" * 64)


def committed() -> dict[str, float]:
    return json.loads(THRESHOLDS_FILE.read_text(encoding="utf-8"))


def test_report_has_a_recommended_threshold_per_evaluated_module(fresh_run):
    for entry in fresh_run["modules"].values():
        if entry["status"] == "evaluated":
            rec = entry["recommended_threshold"]
            assert rec in GRID
            assert entry["at_recommended_threshold"]["threshold"] == rec


def test_committed_defaults_match_the_evaluation(fresh_run):
    """Fails after a rule change that moves a best F1: run `python eval/run.py --write-thresholds`, then copy the
    values into api/src/investwatch_api/thresholds.py DEFAULTS and events.DEFAULT_THRESHOLDS (ADR 0316)."""
    expected = committed()
    for module, entry in fresh_run["modules"].items():
        if entry["status"] == "evaluated" and entry["recommended_threshold"] is not None:
            assert entry["recommended_threshold"] == expected[module], module


def test_api_defaults_are_a_copy_of_the_file():
    tree = ast.parse(API_THRESHOLDS.read_text(encoding="utf-8"))
    defaults = next(ast.literal_eval(n.value) for n in ast.walk(tree)
                    if isinstance(n, ast.Assign) and any(getattr(t, "id", None) == "DEFAULTS" for t in n.targets))
    assert defaults == committed()


def test_analytics_fallback_is_a_copy_of_the_file():
    assert events.DEFAULT_THRESHOLDS == committed()
