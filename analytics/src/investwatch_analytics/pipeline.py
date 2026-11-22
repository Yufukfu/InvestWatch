"""Pure pipeline: one ScrapedDocument -> zero or more Findings. No I/O, deterministic given `now` and `new_id`.

A document yields at most one finding per module: M2, or M1 (plus M3 against the publisher when the advisory
offer is the publisher's own), or M3 (change analytics-m1-m3, design decisions 1-2 and 9).

Preprocessing extras (change analytics-embeddings, ADR 0313/0314), each injected and off by default:
`gate` (investment topic gate; drops a third_party/unknown document with no investment signal), `embedder`
(document vector; sets `model.embedder`; cached by the stored `content_hash`), `neardup` (MinHash index; groups near-identical documents and adds
one summary sentence naming the original). Order: empty text, route, gate, embed, near-dup, modules.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
from typing import TYPE_CHECKING

from .config import GateSettings
from .gate import GateDecision, GateTerms, evaluate, load_terms
from .models import Finding, ScrapedDocument
from .modules import m1, m2, m3
from .modules.advertiser import build_advertiser
from .modules.router import route
from .preprocessing import preprocess
from .registry import SCAN_MAX as REGISTRY_SCAN_MAX
from .registry import Registry
from .rules.engine import Catalogue, Context, run_rules

if TYPE_CHECKING:
    from .embeddings import Embedder, EmbedOutcome
    from .llm.judge import LlmJudge
    from .neardup import NearDupIndex, NearDupResult

log = logging.getLogger(__name__)
#: Foreign firms without a Polish branch are in M1 scope only through ads aimed at Polish readers (a branch
#: is registered in Poland; #35 review).
FOREIGN_TYPES = {"foreign_no_branch"}
#: Routing (the registry match) and the M1/M3 rules see at most this prefix of the text, so one hostile 2 MB page
#: cannot tie up the worker (#35 review 2, item 8). A prefix keeps every evidence quote a substring of the original.
SCAN_MAX = REGISTRY_SCAN_MAX


@dataclass(frozen=True)
class SignalCatalogues:
    m1: Catalogue
    m3: Catalogue


@dataclass(frozen=True)
class Gate:
    settings: GateSettings
    terms: GateTerms

    @classmethod
    def from_settings(cls, settings: GateSettings, terms: GateTerms | None = None) -> "Gate":
        return cls(settings, terms or _default_terms())


@lru_cache(maxsize=1)
def _default_terms() -> GateTerms:
    return load_terms()


@dataclass(frozen=True)
class Analysis:
    """Findings plus what the worker needs beyond them: the gate decision (counter) and the near-dup group
    (one `finding.high_risk` per group and module)."""

    findings: list[Finding] = field(default_factory=list)
    gate: GateDecision | None = None
    neardup: "NearDupResult | None" = None
    embedding: "EmbedOutcome | None" = None


@lru_cache(maxsize=1)
def default_signal_catalogues() -> SignalCatalogues:
    """The shipped M1/M3 catalogues, loaded once. Callers load them at startup so a bad YAML fails there."""
    return SignalCatalogues(m1=Catalogue.load_module("M1"), m3=Catalogue.load_module("M3"))


def analyze(
    doc: ScrapedDocument,
    *,
    registry: Registry,
    catalogue: Catalogue,
    now: datetime | None = None,
    new_id: Callable[[], str] = lambda: str(uuid.uuid4()),
    signals: SignalCatalogues | None = None,
    judge: "LlmJudge | None" = None,
    gate: Gate | None = None,
    embedder: "Embedder | None" = None,
    neardup: "NearDupIndex | None" = None,
) -> list[Finding]:
    """The findings of `analyze_document`; kept for callers that need only them (CLI, evaluation)."""
    return analyze_document(doc, registry=registry, catalogue=catalogue, now=now, new_id=new_id, signals=signals,
                            judge=judge, gate=gate, embedder=embedder, neardup=neardup).findings


def analyze_document(
    doc: ScrapedDocument,
    *,
    registry: Registry,
    catalogue: Catalogue,
    now: datetime | None = None,
    new_id: Callable[[], str] = lambda: str(uuid.uuid4()),
    signals: SignalCatalogues | None = None,
    judge: "LlmJudge | None" = None,
    gate: Gate | None = None,
    embedder: "Embedder | None" = None,
    neardup: "NearDupIndex | None" = None,
) -> Analysis:
    """`judge`, `embedder` and `neardup` are the only I/O and are injected: None (the default) is off.

    None of them can fail the document: the embedder and the index never raise (they return a status or None).
    """
    now = now or datetime.now(timezone.utc)
    begin = getattr(judge, "begin_document", None)
    if begin is not None:
        begin()  # the per-document LLM budget (ADR 0310) covers every module of this document
    pre = preprocess(doc.text)
    if pre.is_empty:
        _skipped(doc, "empty_text")
        return Analysis()
    signals = signals or default_signal_catalogues()
    scan = doc if len(doc.text) <= SCAN_MAX else doc.model_copy(update={"text": doc.text[:SCAN_MAX]})
    if scan is not doc:
        # Not silent: content past the cap is not routed or checked by M1/M3 (an accepted evasion, follow-ups).
        log.info("text truncated", extra={"document_id": doc.id, "reason": "text_truncated",
                                          "text_length": len(doc.text), "scanned": SCAN_MAX})
    scan_pre = pre if scan is doc else preprocess(scan.text)
    r = route(scan, registry)
    ctx = Context(doc=scan, pre=scan_pre, firm_match=r.firm_match, registry=registry)
    m2_ctx = Context(doc=doc, pre=pre, firm_match=r.firm_match, registry=registry)  # M2 rules see the whole text
    findings: list[Finding] = []
    decision = None
    if gate is not None:
        decision = evaluate(scan_pre.normalized, source_kind=doc.source_kind, firm_matched=r.firm_match is not None,
                            terms=gate.terms, settings=gate.settings)
        if not decision.passed:
            _skipped(doc, **decision.log_extra())
            return Analysis(gate=decision)
    # The cache key is the document's stored content_hash (ADR 0105); without one the vector is not cached.
    embedding = embedder.embed(pre.normalized, doc.content_hash) if embedder is not None else None
    group = neardup.observe(doc.id, pre.normalized, doc.url) if neardup is not None else None
    if r.module is None:
        _skipped(doc, r.reason)
        return Analysis(gate=decision, neardup=group, embedding=embedding)
    if r.module == "M2":
        findings.append(m2.build_finding(m2_ctx, catalogue, now=now, new_id=new_id, judge=judge))
    elif r.module == "M1":
        findings += _m1_and_m3(ctx, signals, now=now, new_id=new_id, judge=judge)
    else:
        m3_rules = run_rules(signals.m3, ctx, judge, module="M3", module_context=m3.M3_CONTEXT)
        if m3.has_advisory(m3_rules):
            findings.append(m3.build_finding(ctx, signals.m3, advertiser=build_advertiser(doc, registry), now=now,
                                             new_id=new_id, rules=m3_rules, judge=judge))
        else:
            _skipped(doc, "no_signals")
    findings = [_with_preprocessing(f, embedding, group) for f in findings]
    for f in findings:
        log.info("finding built", extra={"document_id": doc.id, "finding_module": f.module, "score": f.score})
    return Analysis(findings=findings, gate=decision, neardup=group, embedding=embedding)


def _with_preprocessing(finding: Finding, embedding: "EmbedOutcome | None", group: "NearDupResult | None") -> Finding:
    """`model.embedder` from the vector actually used, plus the near-dup summary sentence (no contract change)."""
    update: dict = {}
    if embedding is not None and finding.model is not None:  # outcome.model is set iff a vector was used
        update["model"] = finding.model.model_copy(update={"embedder": embedding.model})
    sentence = neardup_sentence(group)
    if sentence:
        update["summary"] = f"{finding.summary} {sentence}" if finding.summary else sentence
    return finding.model_copy(update=update) if update else finding


def _plural_materials(n: int) -> str:
    """Polish plural of `materiał` after a number (1 materiał, 2-4 materiały, 5+ materiałów; 12-14 materiałów)."""
    if n == 1:
        return "materiał"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return "materiały"
    return "materiałów"


def neardup_sentence(group: "NearDupResult | None") -> str | None:
    """One Polish sentence for a non-original group member; None for the original, a lone member or no index."""
    if group is None or group.is_original or group.members < 2 or not group.original_url:
        return None
    return (f"Treść niemal identyczna z wcześniej przeanalizowanym materiałem: {group.original_url} "
            f"(w grupie {group.members} {_plural_materials(group.members)}).")


def _m1_and_m3(ctx: Context, signals: SignalCatalogues, *, now: datetime, new_id: Callable[[], str],
               judge: "LlmJudge | None" = None) -> list[Finding]:
    advertiser = build_advertiser(ctx.doc, ctx.registry)
    out: list[Finding] = []
    finding = m1.build_finding(ctx, signals.m1, advertiser=advertiser, now=now, new_id=new_id, judge=judge)
    s17 = next((r for r in finding.rules if r.rule_id == "S1.7"), None)
    foreign = ctx.firm_match is not None and ctx.firm_match.firm.type in FOREIGN_TYPES
    if foreign and s17 is not None and s17.result == "pass":
        # Out of scope as a whole (routing requirement): no M1, and no M3 alongside it either.
        _skipped(ctx.doc, "not_targeting_poland")
        return []
    out.append(finding)
    m3_rules = run_rules(signals.m3, ctx, judge, module="M3", module_context=m3.M3_CONTEXT)
    if m3.offer_is_publishers(ctx, m3_rules, signals.m3):
        out.append(m3.build_finding(ctx, signals.m3, advertiser=advertiser, now=now, new_id=new_id, rules=m3_rules,
                                  judge=judge))
    return out


def _skipped(doc: ScrapedDocument, reason: str, **extra) -> None:  # extra: figures only, never document text
    log.info("document skipped", extra={"document_id": doc.id, "source_kind": doc.source_kind, "reason": reason,
                                        **extra})
