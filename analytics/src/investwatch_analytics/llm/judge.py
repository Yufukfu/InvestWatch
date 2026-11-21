"""The LLM judge interface shared by M1, M2 and M3 (design §1-2, ADR 0309).

Rule code never imports the HTTP client: the engine turns deferred rule results into `SemanticCheck`s, asks an
`LlmJudge` once per module, and merges the `LlmVerdict`s it gets back. M1/M3 code imports these types only.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal, Protocol

from ..preprocessing import Sentence

Result = Literal["fail", "pass", "not_applicable", "uncertain"]
JudgeStatus = Literal["ok", "disabled", "unavailable", "malformed", "budget_exhausted", "nothing_to_ask"]


@dataclass(frozen=True)
class SemanticCheck:
    """One question for the LLM: a deferred rule, its catalogue `llm.question`, the results it may answer."""

    rule_id: str
    question: str
    allowed: tuple[Result, ...] = ("fail", "pass", "uncertain")


@dataclass(frozen=True)
class LlmVerdict:
    """A validated answer. `evidence` is already verified: a verbatim substring of the document, or None."""

    rule_id: str
    result: Result
    evidence: str | None
    explanation: str


@dataclass(frozen=True)
class JudgeOutcome:
    verdicts: dict[str, LlmVerdict] = field(default_factory=dict)
    model: str | None = None      # the model that produced the verdicts; None when none was used
    status: JudgeStatus = "ok"


class LlmJudge(Protocol):
    def judge(
        self,
        *,
        module: str,
        module_context: str,
        text: str,
        content_hash: str,
        sentences: Sequence[Sentence],
        checks: Sequence[SemanticCheck],
    ) -> JudgeOutcome: ...
