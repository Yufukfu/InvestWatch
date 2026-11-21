"""LLM layer (change analytics-llm-p0): OpenAI-compatible client, prompt, chunking, judge, cache.

The rules always run first; the LLM only decides checks the rules defer (ADR 0309). Every failure path
ends in the rules-only result.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..config import LlmSettings
    from .judge import HttpJudge


def build_judge(settings: "LlmSettings") -> "HttpJudge | None":
    """The judge for the worker and the CLI; None when `LLM_BASE_URL` is empty (rules-only)."""
    if not settings.enabled:
        return None
    from .judge import HttpJudge

    return HttpJudge(settings)
