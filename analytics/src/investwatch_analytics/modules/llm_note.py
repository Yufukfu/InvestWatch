"""What M1, M2 and M3 findings say about the LLM: `model.llm` and the Polish mode sentence (design §8)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..models import RuleResult

if TYPE_CHECKING:
    from ..llm.judge import LlmJudge


def llm_rule_ids(rules: list[RuleResult]) -> list[str]:
    return [r.rule_id for r in rules if r.method in ("llm", "hybrid")]


def llm_model_used(rules: list[RuleResult], judge: "LlmJudge | None") -> str | None:
    """The model name only when at least one result was decided with it; None otherwise (ADR 0309)."""
    return judge.model_name if judge is not None and llm_rule_ids(rules) else None


def mode_sentence(rules: list[RuleResult], llm_model: str | None) -> str:
    ids = llm_rule_ids(rules)
    if llm_model and ids:
        return f"Sygnały {', '.join(ids)} rozstrzygnięto z pomocą modelu językowego ({llm_model})."
    return "Tryb regułowy (bez modelu językowego)."
