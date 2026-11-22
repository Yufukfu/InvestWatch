"""gold-set-evaluation: "Recommended threshold" and "Default thresholds from the evaluation" (ADR 0316)."""

from __future__ import annotations

import ast
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from investwatch_analytics import events
from investwatch_analytics.evaluation import __main__ as cli
from investwatch_analytics.evaluation import runner
from investwatch_analytics.evaluation.gold import load_gold
from investwatch_analytics.evaluation.metrics import GRID, f1_plateau, recommended_threshold
from investwatch_analytics.evaluation.runner import (
    DEFAULT_GOLD,
    DEFAULT_REGISTRY,
    LLM_MEASURED_MODULES,
    LLM_RUN_FILE,
    THRESHOLD_FLOORS,
    THRESHOLDS_FILE,
    default_threshold,
    evaluate,
    llm_measured_defaults,
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
    assert f1_plateau(points({})) is None


def test_plateau_within_002_of_the_best_takes_its_higher_end():
    curve = points({0.3: 0.80, 0.35: 0.79, 0.4: 0.785, 0.45: 0.70})
    assert f1_plateau(curve) == [0.3, 0.4]
    assert recommended_threshold(curve) == 0.4


def test_just_outside_the_plateau_is_not_chosen():
    curve = points({0.3: 0.80, 0.35: 0.779})
    assert f1_plateau(curve) == [0.3, 0.3]
    assert recommended_threshold(curve) == 0.3


def test_m3_floor_is_the_s34_gate_cap():
    from investwatch_analytics.modules.m3 import GATE_CAP

    assert THRESHOLD_FLOORS == {"M3": GATE_CAP}


def test_default_is_the_recommendation_raised_to_the_floor():
    assert default_threshold("M3", 0.25) == 0.4
    assert default_threshold("M3", 0.55) == 0.55
    assert default_threshold("M2", 0.25) == 0.25
    assert default_threshold("M3", None) is None


def test_write_thresholds_keeps_modules_without_a_recommendation(tmp_path):
    path = tmp_path / "thresholds.json"
    path.write_text('{"M1": 0.6, "M2": 0.5, "M3": 0.7}\n', encoding="utf-8")
    report = {"modules": {"M1": {"status": "evaluated", "default_threshold": 0.65},
                          "M2": {"status": "evaluated", "default_threshold": None},
                          "M3": {"status": "not_run", "points": []}}}
    assert write_thresholds(path, report) == {"M1": 0.65, "M2": 0.5, "M3": 0.7}
    assert json.loads(path.read_text(encoding="utf-8")) == {"M1": 0.65, "M2": 0.5, "M3": 0.7}
    assert path.read_text(encoding="utf-8").endswith("\n")


def test_write_thresholds_overrides_win_over_the_rules_only_run(tmp_path):
    path = tmp_path / "thresholds.json"
    path.write_text('{"M1": 0.6, "M2": 0.5, "M3": 0.7}\n', encoding="utf-8")
    report = {"modules": {"M1": {"status": "evaluated", "default_threshold": 0.65},
                          "M2": {"status": "evaluated", "default_threshold": 0.1}}}
    assert write_thresholds(path, report, {"M1": 0.75}) == {"M1": 0.75, "M2": 0.1, "M3": 0.7}


def test_cli_refuses_an_llm_measured_default_off_the_plateau(tmp_path, capsys, monkeypatch):
    path = tmp_path / "thresholds.json"
    path.write_text('{"M1": 0.6, "M2": 0.5, "M3": 0.7}\n', encoding="utf-8")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(runner, "LLM_MEASURED_DEFAULTS", {"M1": 0.5})  # F1 0.952 on the recorded run, best 1.0
    assert cli.main(["--write-thresholds", str(path)]) == 2
    assert json.loads(path.read_text(encoding="utf-8")) == {"M1": 0.6, "M2": 0.5, "M3": 0.7}
    assert "plateau" in capsys.readouterr().err


def test_write_thresholds_without_a_previous_file(tmp_path):
    path = tmp_path / "thresholds.json"
    report = {"modules": {"M2": {"status": "evaluated", "default_threshold": 0.25}}}
    with pytest.raises(ValueError):
        write_thresholds(path, report)  # M1/M3 would have no value at all


def test_write_thresholds_with_llm_is_refused_before_analysis(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://ollama:11434/v1")
    monkeypatch.setattr(cli, "evaluate", lambda *a, **k: pytest.fail("analyzed"))
    assert cli.main(["--llm", "--write-thresholds", str(tmp_path / "t.json")]) == 2
    assert "rules-only" in capsys.readouterr().err


def test_write_thresholds_refused_after_a_crashed_document(tmp_path, capsys, monkeypatch):
    path = tmp_path / "thresholds.json"
    path.write_text('{"M1": 0.6, "M2": 0.5, "M3": 0.7}\n', encoding="utf-8")

    def boom(self, doc, **kw):
        raise RuntimeError("bug")

    monkeypatch.setattr(cli.load_build().__class__, "analyze", boom)
    assert cli.main(["--write-thresholds", str(path)]) == 1
    assert json.loads(path.read_text(encoding="utf-8")) == {"M1": 0.6, "M2": 0.5, "M3": 0.7}
    assert "not written" in capsys.readouterr().err


@pytest.mark.parametrize("content", ["{not json", "[1, 2]"])
def test_unreadable_thresholds_file_exits_2(tmp_path, capsys, content):
    path = tmp_path / "thresholds.json"
    path.write_text(content, encoding="utf-8")
    assert cli.main(["--write-thresholds", str(path)]) == 2
    assert "thresholds" in capsys.readouterr().err


def test_cli_write_thresholds(tmp_path, capsys, monkeypatch):
    path = tmp_path / "thresholds.json"
    path.write_text('{"M1": 0.6, "M2": 0.5, "M3": 0.7}\n', encoding="utf-8")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    code = cli.main(["--write-thresholds", str(path)])
    report = json.loads(capsys.readouterr().out)
    assert code in (0, 1)
    written = json.loads(path.read_text(encoding="utf-8"))
    llm = llm_measured_defaults()
    for module, entry in report["modules"].items():
        if module in llm:
            assert written[module] == llm[module]  # kept from the recorded LLM run (ADR 0318)
        elif entry.get("default_threshold") is not None:
            assert written[module] == entry["default_threshold"]


@pytest.fixture(scope="module")
def fresh_run():
    build = load_build()
    items = load_gold(DEFAULT_GOLD, build.catalogues)
    return evaluate(items, registry=Registry.from_csv(DEFAULT_REGISTRY), build=build,
                    now=datetime(2026, 11, 22, tzinfo=timezone.utc), gold_sha256="0" * 64)


def committed() -> dict[str, float]:
    return json.loads(THRESHOLDS_FILE.read_text(encoding="utf-8"))


def test_report_has_a_recommended_threshold_per_evaluated_module(fresh_run):
    for module, entry in fresh_run["modules"].items():
        if entry["status"] == "evaluated":
            rec = entry["recommended_threshold"]
            assert rec in GRID
            assert entry["at_recommended_threshold"]["threshold"] == rec
            assert entry["f1_plateau"][1] == rec
            assert entry["default_threshold"] == max(rec, THRESHOLD_FLOORS.get(module, 0.0))
            assert entry["at_default_threshold"]["threshold"] == entry["default_threshold"]
            assert entry["at_adr_0305_default"]["threshold"] == {"M1": 0.6, "M2": 0.5, "M3": 0.7}[module]


def test_committed_defaults_match_the_evaluation(fresh_run):
    """Fails after a rule change that moves a best F1: run `python eval/run.py --write-thresholds`, then copy the
    values into api/src/investwatch_api/thresholds.py DEFAULTS and events.DEFAULT_THRESHOLDS (ADR 0316).
    LLM-measured modules (ADR 0318) are checked against the recorded LLM run instead."""
    expected = committed()
    for module, entry in fresh_run["modules"].items():
        if module in LLM_MEASURED_MODULES:
            continue
        if entry["status"] == "evaluated" and entry["default_threshold"] is not None:
            assert entry["default_threshold"] == expected[module], module


def llm_run() -> dict:
    return json.loads(LLM_RUN_FILE.read_text(encoding="utf-8"))


def test_llm_measured_default_is_on_the_recorded_runs_plateau():
    """ADR 0318: M1's default is Damian's choice on the F1 plateau of the committed `run.py --llm` gold run."""
    assert llm_measured_defaults() == {m: committed()[m] for m in LLM_MEASURED_MODULES}
    assert committed()["M1"] == 0.75
    m1 = llm_run()["modules"]["M1"]
    assert m1["f1_plateau"] == f1_plateau(m1["points"]) == [0.75, 0.8]


def test_a_default_off_the_recorded_plateau_is_refused(tmp_path, monkeypatch):
    run = llm_run()
    for p in run["modules"]["M1"]["points"]:
        if p["threshold"] == 0.75:
            p["f1"] = 0.5
    path = tmp_path / "run.json"
    path.write_text(json.dumps(run), encoding="utf-8")
    with pytest.raises(ValueError, match="plateau"):
        llm_measured_defaults(path)


def test_llm_run_was_measured_on_this_gold_set():
    """A changed gold set fails here: re-run `python eval/run.py --llm` and replace the run file (ADR 0318)."""
    run = llm_run()
    assert run["gold_sha256"] == hashlib.sha256(DEFAULT_GOLD.read_bytes()).hexdigest()
    assert run["model"] and run["documents"] == len(DEFAULT_GOLD.read_text(encoding="utf-8").splitlines())


def test_llm_run_was_measured_on_these_rules(fresh_run):
    """A rule change that moves an LLM-measured module's rules-only default fails here: the recorded LLM run no
    longer describes this build. Re-run `python eval/run.py --llm` and replace the run file (ADR 0318)."""
    run = llm_run()
    for module in LLM_MEASURED_MODULES:
        rules_only = fresh_run["modules"][module]["default_threshold"]
        assert rules_only == run["modules"][module]["rules_only_default_threshold"], module


def test_rules_only_fallback_keeps_precision_at_llm_measured_defaults(fresh_run):
    """With the LLM down (rules-only), an LLM-measured default may lose recall but must raise no false alert."""
    for module in LLM_MEASURED_MODULES:
        point = next(p for p in fresh_run["modules"][module]["points"] if p["threshold"] == committed()[module])
        assert point["fp"] == 0 and point["tp"] > 0, (module, point)


def test_api_defaults_are_a_copy_of_the_file():
    tree = ast.parse(API_THRESHOLDS.read_text(encoding="utf-8"))
    defaults = next(ast.literal_eval(n.value) for n in ast.walk(tree)
                    if isinstance(n, ast.Assign) and any(getattr(t, "id", None) == "DEFAULTS" for t in n.targets))
    assert defaults == committed()


def test_analytics_fallback_is_a_copy_of_the_file():
    assert events.DEFAULT_THRESHOLDS == committed()
