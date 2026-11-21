"""M1/M3 scores: σ(bias + Σ wᵢ·xᵢ) with weights from the signal catalogue (change analytics-m1-m3, design 10)."""

from __future__ import annotations

import math

from ..models import RuleResult
from .engine import Catalogue

#: x per result: present 1, a candidate only the LLM can confirm 0.5, absent or not judged 0.
X_VALUE = {"fail": 1.0, "uncertain": 0.5}


def sigmoid_score(rules: list[RuleResult], catalogue: Catalogue) -> float:
    z = catalogue.bias
    for r in rules:
        try:
            spec = catalogue.get(r.rule_id)
        except KeyError:
            continue
        z += spec.weight * X_VALUE.get(r.result, 0.0)
    if z < -700:  # math.exp overflows past ~709
        return 0.0
    return round(1.0 / (1.0 + math.exp(-z)), 3)


def capped(score: float, cap: float) -> float:
    return min(score, cap)
