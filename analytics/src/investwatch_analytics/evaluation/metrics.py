"""Confusion counts and ratios, the same way `GET /api/calibration` computes them.

Source of the conventions: openspec/specs/rest-api/spec.md, requirement "Calibration curve" (code:
api/src/investwatch_api/routes/calibration.py). The services share no code, so the parity tests in
tests/test_eval_metrics.py pin the spec scenario: a positive prediction is `score >= threshold`; precision is
1.0 when nothing is predicted positive, recall 0.0 without positives, f1 0.0 when both are 0; f1 comes from the
unrounded ratios; every ratio is rounded to 3 decimals.
"""

from __future__ import annotations

from collections.abc import Iterable

GRID = tuple(round(0.05 * i, 2) for i in range(1, 20))  # 0.05 .. 0.95, the API's grid
RESULTS = ("fail", "pass", "uncertain", "not_applicable")


def confusion(pairs: Iterable[tuple[float, bool]], threshold: float) -> tuple[int, int, int, int]:
    """(tp, fp, fn, tn) of (score, is_positive) pairs at one threshold."""
    tp = fp = fn = tn = 0
    for score, positive in pairs:
        predicted = score >= threshold
        if positive and predicted:
            tp += 1
        elif predicted:
            fp += 1
        elif positive:
            fn += 1
        else:
            tn += 1
    return tp, fp, fn, tn


def ratios(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    precision = tp / (tp + fp) if tp + fp else 1.0  # nothing predicted positive: no false alarms
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return round(precision, 3), round(recall, 3), round(f1, 3)


def point(threshold: float, tp: int, fp: int, fn: int, tn: int) -> dict:
    precision, recall, f1 = ratios(tp, fp, fn)
    return {"threshold": threshold, "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": precision, "recall": recall, "f1": f1}


def curve(pairs: Iterable[tuple[float, bool]]) -> list[dict]:
    """One point per grid threshold, ascending; the shape of a `GET /api/calibration` point."""
    pairs = list(pairs)
    return [point(t, *confusion(pairs, t)) for t in GRID]


def _counts(observations: list[tuple[bool, bool]]) -> dict:
    tp = sum(1 for pos, flag in observations if pos and flag)
    fp = sum(1 for pos, flag in observations if not pos and flag)
    fn = sum(1 for pos, flag in observations if pos and not flag)
    tn = sum(1 for pos, flag in observations if not pos and not flag)
    precision, recall, f1 = ratios(tp, fp, fn)
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": precision, "recall": recall, "f1": f1}


def rule_metrics(observations: Iterable[tuple[str, str | None]]) -> dict:
    """Metrics of one rule or signal from (gold label, predicted result or None when there is no result).

    Gold `fail` is a positive, `pass` a negative, `not_applicable` stays out of the counts. Readings:
    `strict` flags only `fail`; `review` also flags `uncertain` (what the dashboard shows as "do weryfikacji").
    An applicability error is gold `not_applicable` with an applicable prediction, or a labeled rule the
    pipeline called `not_applicable`.
    """
    labels = {"fail": 0, "pass": 0, "not_applicable": 0}
    strict: list[tuple[bool, bool]] = []
    review: list[tuple[bool, bool]] = []
    uncertain = errors = 0
    for gold, predicted in observations:
        if predicted is not None and predicted not in RESULTS:
            raise ValueError(f"unknown rule result {predicted!r}")
        labels[gold] += 1
        if predicted == "uncertain":
            uncertain += 1
        if gold == "not_applicable":
            if predicted not in (None, "not_applicable"):
                errors += 1
            continue
        if predicted == "not_applicable":
            errors += 1
        positive = gold == "fail"
        strict.append((positive, predicted == "fail"))
        review.append((positive, predicted in ("fail", "uncertain")))
    return {"labels": labels, "strict": _counts(strict), "review": _counts(review),
            "uncertain": uncertain, "applicability_errors": errors}
