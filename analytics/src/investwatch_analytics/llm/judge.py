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
    #: The model reported as `model.llm` on a finding when one of its verdicts was used.
    model_name: str

    def judge(
        self,
        *,
        module: str,
        module_context: str,
        text: str,
        content_hash: str | None,
        sentences: Sequence[Sentence],
        checks: Sequence[SemanticCheck],
    ) -> JudgeOutcome: ...


# ---- HTTP judge (task group 7) ---------------------------------------------------------------------

import logging  # noqa: E402
import re  # noqa: E402
import unicodedata  # noqa: E402
from typing import Any  # noqa: E402

from pydantic import BaseModel, ConfigDict, Field, ValidationError  # noqa: E402

from ..config import LlmSettings  # noqa: E402
from .chunking import Chunk, split_chunks  # noqa: E402
from .client import ChatClient, LlmError, LlmMalformed, LlmUnavailable  # noqa: E402
from .prompt import prompt_version, system_prompt, user_message  # noqa: E402
from .cache import LlmCache, cache_key  # noqa: E402
import time  # noqa: E402

log = logging.getLogger(__name__)
MIN_QUOTE_CHARS = 8
MAX_QUOTE_CHARS = 400
MAX_EXPLANATION_CHARS = 500
#: Worst first: the merged verdict per check is the worst across chunks (ADR 0310).
SEVERITY = {"fail": 3, "uncertain": 2, "pass": 1, "not_applicable": 0}
UNCONFIRMED = "Nie udało się potwierdzić cytatu w treści dokumentu; wymaga weryfikacji."
NO_EXPLANATION = "Model nie podał uzasadnienia."


class _Item(BaseModel):
    """One answer item, validated on its own: a bad item is dropped, not the whole response."""

    model_config = ConfigDict(extra="ignore")
    rule_id: str
    result: str
    evidence_quote: str | None = Field(default=None, max_length=MAX_QUOTE_CHARS)
    explanation: str = Field(max_length=MAX_EXPLANATION_CHARS)


def _clean(text: str) -> str:
    """Model output shown in the dashboard: control and format characters (bidi overrides too) become spaces."""
    return " ".join("".join(" " if unicodedata.category(ch) in ("Cc", "Cf") else ch for ch in text).split())


def verify_quote(chunk: str, quote: str | None) -> str | None:
    """The quote as it appears in the chunk (exact, else whitespace-insensitive), or None.

    Quotes under `MIN_QUOTE_CHARS` never verify: one common word or letter would match almost any text.
    """
    if quote is None:
        return None
    q = quote.strip()
    if len(q) < MIN_QUOTE_CHARS:
        return None
    if q in chunk:
        return q
    m = re.search(r"\s+".join(map(re.escape, q.split())), chunk)
    # A match far longer than the quote spans a huge whitespace run: not the passage the model quoted.
    if m is None or len(m.group(0)) > 2 * MAX_QUOTE_CHARS:
        return None
    return m.group(0)


def _verdict(item: _Item, chunk: str) -> LlmVerdict:
    # Small models often send "" for "no quote": a blank quote is no quote, not an unverifiable one.
    given = item.evidence_quote if item.evidence_quote is not None and item.evidence_quote.strip() else None
    quote = verify_quote(chunk, given)
    explanation = _clean(item.explanation) or NO_EXPLANATION
    if given is not None and quote is None:
        return LlmVerdict(item.rule_id, "uncertain", None, UNCONFIRMED)
    if item.result in ("fail", "uncertain") and quote is None:
        return LlmVerdict(item.rule_id, "uncertain", None, UNCONFIRMED)
    return LlmVerdict(item.rule_id, item.result, quote, explanation)  # type: ignore[arg-type]


def parse_results(content: dict[str, Any], chunk: str, checks: Sequence[SemanticCheck]) -> dict[str, LlmVerdict]:
    allowed = {c.rule_id: set(c.allowed) for c in checks}
    out: dict[str, LlmVerdict] = {}
    for raw in content.get("results", []):
        try:
            item = _Item.model_validate(raw)
        except ValidationError:
            continue
        if item.rule_id not in allowed or item.result not in allowed[item.rule_id] or item.rule_id in out:
            continue
        out[item.rule_id] = _verdict(item, chunk)
    return out


def merge_chunks(per_chunk: list[dict[str, LlmVerdict]]) -> dict[str, LlmVerdict]:
    """Worst chunk wins per check; ties go to the earliest chunk."""
    merged: dict[str, LlmVerdict] = {}
    for verdicts in per_chunk:
        for rule_id, v in verdicts.items():
            if rule_id not in merged or SEVERITY[v.result] > SEVERITY[merged[rule_id].result]:
                merged[rule_id] = v
    return merged


class HttpJudge:
    """`LlmJudge` over an OpenAI-compatible endpoint. Never raises: every failure is a `JudgeOutcome` status."""

    def __init__(self, settings: LlmSettings, *, client: ChatClient | None = None, redis: Any = None,
                 clock: Any = time.monotonic):
        self.settings = settings
        self.model_name = settings.model
        self._client = client or ChatClient(settings)
        self._cache = LlmCache(redis, settings.cache_ttl_s) if redis is not None else None
        self._clock = clock
        self._deadline: float | None = None      # per-document budget (ADR 0310), set by begin_document()
        self._failures = 0                      # consecutive unavailable outcomes (circuit breaker)
        self._open_until: float | None = None

    def begin_document(self) -> None:
        """Start the per-document wall-clock budget; the pipeline calls this once per document."""
        self._deadline = self._clock() + self.settings.doc_budget_s

    def _breaker_open(self) -> bool:
        if self._open_until is None:
            return False
        if self._clock() >= self._open_until:
            self._open_until = None  # half-open: one call may try; a failure reopens at once
            self._failures = self.settings.breaker_failures - 1
            return False
        return True

    def _record(self, ok: bool) -> None:
        if ok:
            self._failures, self._open_until = 0, None
            return
        self._failures += 1
        if self._failures >= self.settings.breaker_failures:
            self._open_until = self._clock() + self.settings.breaker_cooldown_s

    def judge(
        self,
        *,
        module: str,
        module_context: str,
        text: str,
        content_hash: str | None,
        sentences: Sequence[Sentence],
        checks: Sequence[SemanticCheck],
    ) -> JudgeOutcome:
        if not checks:
            return JudgeOutcome(status="nothing_to_ask")
        system = system_prompt(module, module_context, checks)
        chunks, truncated = split_chunks(text, sentences, chunk_chars=self.settings.chunk_chars,
                                         max_chunks=self.settings.max_chunks)
        if truncated:
            log.info("llm input truncated", extra={"reason": "llm_truncated", "llm_module": module,
                                                   "chunks": len(chunks)})
        version = prompt_version(system)
        rule_ids = [c.rule_id for c in checks]
        # The key is the document's stored `content_hash` (issue #31, ADR 0105); analytics never computes one. A
        # document without it bypasses the cache: a missing hash must not become a key that documents share.
        cache = self._cache if content_hash else None
        per_chunk: list[dict[str, LlmVerdict]] = []
        for index, chunk in enumerate(chunks):
            key = cache_key(module=module, content_hash=content_hash, prompt_version=version,
                            model=self.settings.model, chunk_index=index, chunk_count=len(chunks),
                            chunk_span=(chunk.start, chunk.end), rule_ids=rule_ids) if cache is not None else None
            content = cache.get(key) if cache is not None else None
            if content is None:
                outcome = self._call(system, chunk, module=module, content_hash=content_hash)
                if isinstance(outcome, JudgeOutcome):
                    return outcome
                content = outcome
                if cache is not None:
                    cache.set(key, content)
            per_chunk.append(parse_results(content, chunk.text, checks))
        verdicts = merge_chunks(per_chunk)
        return JudgeOutcome(verdicts=verdicts, model=self.settings.model if verdicts else None, status="ok")

    def _call(self, system: str, chunk: Chunk, *, module: str, content_hash: str | None) -> dict[str, Any] | JudgeOutcome:
        """One request, inside the breaker and the document budget; a failure is a `JudgeOutcome`."""
        if self._breaker_open():
            return self._dropped("unavailable", "llm_breaker_open", module, content_hash)
        timeout = self.settings.timeout_s
        if self._deadline is not None:
            remaining = self._deadline - self._clock()
            if remaining <= 0:
                return self._dropped("budget_exhausted", "llm_budget_exhausted", module, content_hash)
            timeout = min(timeout, remaining)
        try:
            content = self._ask(system, chunk, timeout)
        except LlmError as exc:
            # Only a timeout that actually used up the budget is the document's; an early one (a 3 s connect
            # timeout) is the endpoint's and counts for the breaker (re-review of the whole-branch fixes).
            if exc.reason == "llm_timeout" and self._deadline is not None and self._clock() >= self._deadline - 0.05:
                # The document ran out of time, the endpoint did not fail: no breaker count (whole-branch review).
                return self._dropped("budget_exhausted", "llm_budget_exhausted", module, content_hash)
            if isinstance(exc, LlmUnavailable):
                self._record(ok=False)
            return self._dropped("malformed" if isinstance(exc, LlmMalformed) else "unavailable", exc.reason,
                                 module, content_hash)
        self._record(ok=True)
        return content

    @staticmethod
    def _dropped(status: str, reason: str, module: str, content_hash: str | None) -> JudgeOutcome:
        log.warning("llm verdicts dropped", extra={"reason": reason, "llm_module": module, "content_hash": content_hash})
        return JudgeOutcome(status=status)  # type: ignore[arg-type]

    def _ask(self, system: str, chunk: Chunk, timeout: float | None = None) -> dict[str, Any]:
        try:
            return self._client.complete(system, user_message(chunk.text), timeout_s=timeout)
        except (LlmUnavailable, LlmMalformed):
            raise
        except Exception as exc:  # pragma: no cover - defensive: a judge must never break the document
            raise LlmMalformed(f"unexpected client error ({type(exc).__name__})") from None
