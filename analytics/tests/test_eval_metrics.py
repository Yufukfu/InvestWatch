"""gold-set-evaluation: "Module curve with the API's counting" and "Per-rule and per-signal metrics"."""

from __future__ import annotations

import pytest

from investwatch_analytics.evaluation.metrics import GRID, confusion, curve, ratios, rule_metrics

# rest-api spec "Calibration curve", scenario "Curve from analyst labels".
API_SCENARIO = [(0.9, True), (0.4, True), (0.6, False), (0.2, False)]


def test_grid_is_the_api_grid():
    assert len(GRID) == 19
    assert GRID[0] == 0.05 and GRID[-1] == 0.95
    assert GRID == tuple(round(0.05 * i, 2) for i in range(1, 20))
    assert 0.3 in GRID and 0.7 in GRID  # no float drift such as 0.30000000000000004


def test_confusion_counts():
    assert confusion(API_SCENARIO, 0.5) == (1, 1, 1, 1)
    assert confusion(API_SCENARIO, 0.05) == (2, 2, 0, 0)
    assert confusion(API_SCENARIO, 0.95) == (0, 0, 2, 2)


def test_score_equal_to_threshold_is_predicted_positive():
    assert confusion([(0.5, True)], 0.5) == (1, 0, 0, 0)
    assert confusion([(0.5, True)], 0.55) == (0, 0, 1, 0)
    assert confusion([(0.5, False)], 0.5) == (0, 1, 0, 0)


def test_precision():
    assert ratios(3, 1, 0)[0] == 0.75


def test_precision_when_nothing_predicted_positive():
    assert ratios(0, 0, 4) == (1.0, 0.0, 0.0)


def test_recall():
    assert ratios(1, 0, 3)[1] == 0.25


def test_recall_without_positives():
    assert ratios(0, 2, 0) == (0.0, 0.0, 0.0)


def test_f1_harmonic_mean_from_unrounded_ratios():
    assert ratios(11, 3, 4) == (0.786, 0.733, 0.759)  # rest-api scenario "Labels added to a stored run"
    assert ratios(1, 0, 6) == (1.0, 0.143, 0.25)


def test_f1_zero_when_both_zero():
    assert ratios(0, 1, 1) == (0.0, 0.0, 0.0)


def test_rounding_to_three_decimals():
    assert ratios(1, 2, 0) == (0.333, 1.0, 0.5)
    assert ratios(2, 1, 1) == (0.667, 0.667, 0.667)


def test_curve_matches_the_rest_api_scenario():
    points = curve(API_SCENARIO)
    assert [p["threshold"] for p in points] == list(GRID)
    at = {p["threshold"]: p for p in points}
    assert at[0.5] == {"threshold": 0.5, "tp": 1, "fp": 1, "fn": 1, "tn": 1,
                       "precision": 0.5, "recall": 0.5, "f1": 0.5}


def test_curve_point_without_predictions():
    at = {p["threshold"]: p for p in curve([(0.3, True), (0.1, False)])}
    assert at[0.95] == {"threshold": 0.95, "tp": 0, "fp": 0, "fn": 1, "tn": 1,
                        "precision": 1.0, "recall": 0.0, "f1": 0.0}


def test_curve_of_nothing_is_all_zero_counts():
    assert all((p["tp"], p["fp"], p["fn"], p["tn"]) == (0, 0, 0, 0) for p in curve([]))


# ---- per rule -----------------------------------------------------------------------------------


def test_uncertain_in_both_readings():
    m = rule_metrics([("fail", "uncertain")])
    assert (m["strict"]["tp"], m["strict"]["fn"]) == (0, 1)
    assert (m["review"]["tp"], m["review"]["fn"]) == (1, 0)
    assert m["uncertain"] == 1


def test_uncertain_on_a_negative():
    m = rule_metrics([("pass", "uncertain")])
    assert (m["strict"]["fp"], m["strict"]["tn"]) == (0, 1)
    assert (m["review"]["fp"], m["review"]["tn"]) == (1, 0)


def test_fail_and_pass_counts_and_ratios():
    m = rule_metrics([("fail", "fail"), ("fail", "pass"), ("pass", "fail"), ("pass", "pass"), ("pass", "pass")])
    assert {k: m["strict"][k] for k in ("tp", "fp", "fn", "tn")} == {"tp": 1, "fp": 1, "fn": 1, "tn": 2}
    assert (m["strict"]["precision"], m["strict"]["recall"], m["strict"]["f1"]) == (0.5, 0.5, 0.5)
    assert m["labels"] == {"fail": 2, "pass": 3, "not_applicable": 0}


def test_gold_not_applicable_with_an_applicable_prediction():
    m = rule_metrics([("not_applicable", "fail")])
    assert m["applicability_errors"] == 1
    assert all(m[r][k] == 0 for r in ("strict", "review") for k in ("tp", "fp", "fn", "tn"))


def test_gold_not_applicable_matched():
    m = rule_metrics([("not_applicable", "not_applicable"), ("not_applicable", None)])
    assert m["applicability_errors"] == 0
    assert m["labels"]["not_applicable"] == 2


def test_predicted_not_applicable_on_a_labeled_rule():
    m = rule_metrics([("fail", "not_applicable")])
    assert m["applicability_errors"] == 1
    assert (m["strict"]["fn"], m["review"]["fn"]) == (1, 1)


def test_missing_rule_result_is_not_flagged():
    m = rule_metrics([("fail", None), ("pass", None)])
    for reading in ("strict", "review"):
        assert (m[reading]["fn"], m[reading]["tn"]) == (1, 1)
    assert m["applicability_errors"] == 0


@pytest.mark.parametrize("bad", ["failed", "maybe"])
def test_unknown_predicted_result_is_rejected(bad):
    with pytest.raises(ValueError):
        rule_metrics([("fail", bad)])
