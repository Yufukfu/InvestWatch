"""LLM layer (change analytics-llm-p0): OpenAI-compatible client, prompt, chunking, judge, cache.

The rules always run first; the LLM only decides checks the rules defer (ADR 0309). Every failure path
ends in the rules-only result.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..config import LlmSettings
    from .judge import HttpJudge


def build_judge(settings: "LlmSettings", *, redis: Any = None) -> "HttpJudge | None":
    """The judge for the worker (with its Redis client, for the cache) and the CLI (no cache); None when
    `LLM_BASE_URL` is empty (rules-only)."""
    if not settings.enabled:
        return None
    from .judge import HttpJudge

    return HttpJudge(settings, redis=redis)


def judge_from_env() -> "HttpJudge | None":
    """The judge from `LLM_*` env, without a cache: the gold-set evaluation's `--llm` looks this up."""
    from ..config import LlmSettings

    return build_judge(LlmSettings.from_env())
