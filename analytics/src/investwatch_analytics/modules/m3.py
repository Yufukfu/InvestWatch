"""M3 finding: an offer that may indicate investment advice by an entity outside the KNF registry
(change analytics-m1-m3, design decisions 8, 9, 11, 13). Output: entity data (`advertiser`), offer content
(`content_excerpt`) and location (`url`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import uuid
from collections.abc import Callable
from datetime import datetime

from ..config import PIPELINE_VERSION
from ..models import AdvertiserRef, Finding, ModelInfo, RuleResult
from ..rules import engine
from ..rules.engine import Catalogue, Context, run_rules
from .llm_note import llm_model_used, mode_sentence

if TYPE_CHECKING:
    from ..llm.judge import LlmJudge

#: The module's legal frame for the LLM system prompt (analytics-llm-p0 design §2; annex 3 definition).
M3_CONTEXT = (
    "Module M3: an entity outside the KNF register. Investment advice (art. 76 of the Act on Trading in "
    "Financial Instruments) is a recommendation to buy, sell or hold specific financial instruments, "
    "based on the client's situation. Financial education alone is not advice."
)
from ..rules.m3 import CRYPTO_NOTE, not_found_text
from ..rules.scoring import capped, sigmoid_score
from .excerpt import excerpt

GATE_CAP = 0.4
#: Signals that indicate an offer at all; without one, an M3-only document gets no finding.
ADVISORY = ("S3.2", "S3.3", "S3.4", "S3.5", "S3.8")
PRESENT = ("fail", "uncertain")


def has_advisory(rules: list[RuleResult]) -> bool:
    return any(r.rule_id in ADVISORY and r.result in PRESENT for r in rules)


def score(rules: list[RuleResult], catalogue: Catalogue) -> tuple[float, bool]:
    """σ(bias + Σ w·x), capped at 0.4 unless S3.4 (instrument recommendation) is fail or uncertain."""
    raw = sigmoid_score(rules, catalogue)
    gate_open = any(r.rule_id == "S3.4" and r.result in PRESENT for r in rules)
    return (raw, False) if gate_open else (capped(raw, GATE_CAP), True)


def offer_is_publishers(ctx: Context, rules: list[RuleResult], catalogue: Catalogue) -> bool:
    """For an M1 document: is an S3.3/S3.4 offer the publisher's own?

    The offer is the registered firm's only when every sentence holding it names the firm (design decision 9);
    every rule candidate is checked, plus the result's own quote (an LLM verdict may quote another sentence).
    """
    match = ctx.firm_match
    for r in rules:
        if r.rule_id not in ("S3.3", "S3.4") or r.result not in PRESENT:
            continue
        rule = engine._RULES[r.rule_id](catalogue.get(r.rule_id))
        sentences = rule.candidates(ctx) + ([_sentence_of(ctx, r.evidence)] if r.evidence else [])
        if any(match is None or ctx.registry.find_name(match.firm, s) is None for s in sentences):
            return True
    return False


def _sentence_of(ctx: Context, quote: str) -> str:
    pos = ctx.doc.text.find(quote)
    for s in ctx.pre.sentences:
        if s.start <= pos < s.end:
            return s.text
    return quote


def build_finding(
    ctx: Context,
    catalogue: Catalogue,
    *,
    advertiser: AdvertiserRef,
    now: datetime,
    new_id: Callable[[], str] = lambda: str(uuid.uuid4()),
    rules: list[RuleResult] | None = None,
    judge: "LlmJudge | None" = None,
) -> Finding:
    """`rules` may be precomputed (the pipeline gates on them); `judge` is then only used to name the model."""
    rules = run_rules(catalogue, ctx, judge, module="M3", module_context=M3_CONTEXT) if rules is None else rules
    llm_model = llm_model_used(rules, judge)
    value, was_capped = score(rules, catalogue)
    title, summary = _texts(rules, advertiser, was_capped, not_found_text(ctx.registry), llm_model=llm_model)
    return Finding(
        id=new_id(),
        document_id=ctx.doc.id,
        module="M3",
        score=value,
        status="new",
        title=title,
        summary=summary,
        firm=None,
        advertiser=advertiser,
        rules=rules,
        content_excerpt=excerpt(ctx.doc.text, ctx.pre, rules),
        url=ctx.doc.url,
        platform=ctx.doc.platform,
        detected_at=now,
        updated_at=now,
        model=ModelInfo(pipeline_version=PIPELINE_VERSION, llm=llm_model, embedder=None),
    )


def _texts(rules: list[RuleResult], advertiser: AdvertiserRef, was_capped: bool, not_found: str, *,
           llm_model: str | None = None) -> tuple[str, str]:
    by_id = {r.rule_id: r for r in rules}
    who = advertiser.handle or advertiser.name or "nieznany podmiot"

    def present(sid: str) -> bool:
        return sid in by_id and by_id[sid].result in PRESENT

    def maybe(sid: str, text: str) -> str:
        """A rule candidate is not a finding of fact: say "możliwe" while the signal is `uncertain` (#35 review)."""
        return f"możliwe {text}" if by_id[sid].result == "uncertain" else text

    if present("S3.4"):
        what = maybe("S3.4", "rekomendacje instrumentów finansowych")
        if present("S3.3"):
            what += " (możliwie dopasowane do klienta)" if by_id["S3.3"].result == "uncertain" else " dopasowane do klienta"
    elif present("S3.3"):
        what = maybe("S3.3", "dopasowanie oferty do klienta, bez rekomendacji instrumentów")
    elif present("S3.8"):
        what = "rekomendacje kryptoaktywów (poza art. 2)"
    elif present("S3.5"):
        what = "płatna oferta inwestycyjna"
    else:
        what = "słownictwo usług doradczych"
    title = f"{who}: {what}"
    found = [r for r in rules if r.result == "fail"]
    unsure = [r for r in rules if r.result == "uncertain"]
    parts = [f"{who}: {not_found[0].lower()}{not_found[1:]}."]
    if found:
        parts.append("Wykryte sygnały: " + "; ".join(f"{r.rule_id} {r.name}" for r in found) + ".")
    if unsure:
        parts.append("Do weryfikacji: " + "; ".join(f"{r.rule_id} {r.name}" for r in unsure) + ".")
    if was_capped:
        parts.append("Wynik ograniczony do 0,4: brak rekomendacji konkretnych instrumentów finansowych (art. 76).")
    if "S3.3" in by_id and by_id["S3.3"].result == "pass":
        # ADR 0308: the S3.4 gate flags offers that may indicate advice; art. 76 also needs the client's situation.
        parts.append("Nie potwierdzono personalizacji (potrzeb i sytuacji klienta), której wymaga art. 76 – "
                     "materiał może jedynie wskazywać na doradztwo inwestycyjne.")
    if present("S3.8"):
        parts.append(f"{CRYPTO_NOTE[0].upper()}{CRYPTO_NOTE[1:]}.")
    parts.append(mode_sentence(rules, llm_model))
    return title, " ".join(parts)
