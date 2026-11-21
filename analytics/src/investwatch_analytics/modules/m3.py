"""M3 finding: an offer that may indicate investment advice by an entity outside the KNF registry
(change analytics-m1-m3, design decisions 8, 9, 11, 13). Output: entity data (`advertiser`), offer content
(`content_excerpt`) and location (`url`).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime

from ..config import PIPELINE_VERSION
from ..models import AdvertiserRef, Finding, ModelInfo, RuleResult
from ..rules import engine
from ..rules.engine import Catalogue, Context, run_rules
from ..rules.m3 import CRYPTO_NOTE, not_found_text
from ..rules.scoring import capped, sigmoid_score

EXCERPT_MAX = 500
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
) -> Finding:
    rules = run_rules(catalogue, ctx) if rules is None else rules
    value, was_capped = score(rules, catalogue)
    title, summary = _texts(rules, advertiser, was_capped, not_found_text(ctx.registry))
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
        content_excerpt=ctx.pre.normalized[:EXCERPT_MAX] or None,
        url=ctx.doc.url,
        platform=ctx.doc.platform,
        detected_at=now,
        updated_at=now,
        model=ModelInfo(pipeline_version=PIPELINE_VERSION, llm=None, embedder=None),
    )


def _texts(rules: list[RuleResult], advertiser: AdvertiserRef, was_capped: bool, not_found: str) -> tuple[str, str]:
    by_id = {r.rule_id: r for r in rules}
    who = advertiser.handle or advertiser.name or "nieznany podmiot"

    def present(sid: str) -> bool:
        return sid in by_id and by_id[sid].result in PRESENT

    if present("S3.4"):
        what = "rekomendacje instrumentów finansowych" + (" dopasowane do klienta" if present("S3.3") else "")
    elif present("S3.3"):
        what = "personalizowana oferta bez rekomendacji instrumentów"
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
    if present("S3.8"):
        parts.append(f"{CRYPTO_NOTE[0].upper()}{CRYPTO_NOTE[1:]}.")
    parts.append("Tryb regułowy (bez modelu językowego).")
    return title, " ".join(parts)
