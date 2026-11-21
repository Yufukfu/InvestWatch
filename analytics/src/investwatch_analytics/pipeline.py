"""Pure pipeline: one ScrapedDocument -> zero or more Findings. No I/O, deterministic given `now` and `new_id`.

A document yields at most one finding per module: M2, or M1 (plus M3 against the publisher when the advisory
offer is the publisher's own), or M3 (change analytics-m1-m3, design decisions 1-2 and 9).
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache

from .models import Finding, ScrapedDocument
from .modules import m1, m2, m3
from .modules.advertiser import build_advertiser
from .modules.router import route
from .preprocessing import preprocess
from .registry import Registry
from .rules.engine import Catalogue, Context, run_rules

log = logging.getLogger(__name__)
#: Foreign firms without a Polish branch are in M1 scope only through ads aimed at Polish readers (a branch
#: is registered in Poland; #35 review).
FOREIGN_TYPES = {"foreign_no_branch"}
#: Routing (the registry match) and the M1/M3 rules see at most this prefix of the text, so one hostile 2 MB page
#: cannot tie up the worker (#35 review 2, item 8). A prefix keeps every evidence quote a substring of the original.
SCAN_MAX = 200_000


@dataclass(frozen=True)
class SignalCatalogues:
    m1: Catalogue
    m3: Catalogue


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
) -> list[Finding]:
    now = now or datetime.now(timezone.utc)
    pre = preprocess(doc.text)
    if pre.is_empty:
        _skipped(doc, "empty_text")
        return []
    signals = signals or default_signal_catalogues()
    scan = doc if len(doc.text) <= SCAN_MAX else doc.model_copy(update={"text": doc.text[:SCAN_MAX]})
    scan_pre = pre if scan is doc else preprocess(scan.text)
    r = route(scan, registry)
    ctx = Context(doc=scan, pre=scan_pre, firm_match=r.firm_match, registry=registry)
    m2_ctx = Context(doc=doc, pre=pre, firm_match=r.firm_match, registry=registry)  # M2 rules see the whole text
    findings: list[Finding] = []
    if r.module is None:
        _skipped(doc, r.reason)
        return []
    if r.module == "M2":
        findings.append(m2.build_finding(m2_ctx, catalogue, now=now, new_id=new_id))
    elif r.module == "M1":
        findings += _m1_and_m3(ctx, signals, now=now, new_id=new_id)
    else:
        m3_rules = run_rules(signals.m3, ctx)
        if m3.has_advisory(m3_rules):
            findings.append(m3.build_finding(ctx, signals.m3, advertiser=build_advertiser(doc, registry), now=now,
                                             new_id=new_id, rules=m3_rules))
        else:
            _skipped(doc, "no_signals")
    for f in findings:
        log.info("finding built", extra={"document_id": doc.id, "finding_module": f.module, "score": f.score})
    return findings


def _m1_and_m3(ctx: Context, signals: SignalCatalogues, *, now: datetime, new_id: Callable[[], str]) -> list[Finding]:
    advertiser = build_advertiser(ctx.doc, ctx.registry)
    out: list[Finding] = []
    finding = m1.build_finding(ctx, signals.m1, advertiser=advertiser, now=now, new_id=new_id)
    s17 = next((r for r in finding.rules if r.rule_id == "S1.7"), None)
    foreign = ctx.firm_match is not None and ctx.firm_match.firm.type in FOREIGN_TYPES
    if foreign and s17 is not None and s17.result == "pass":
        # Out of scope as a whole (routing requirement): no M1, and no M3 alongside it either.
        _skipped(ctx.doc, "not_targeting_poland")
        return []
    out.append(finding)
    m3_rules = run_rules(signals.m3, ctx)
    if m3.offer_is_publishers(ctx, m3_rules, signals.m3):
        out.append(m3.build_finding(ctx, signals.m3, advertiser=advertiser, now=now, new_id=new_id, rules=m3_rules))
    return out


def _skipped(doc: ScrapedDocument, reason: str, **extra) -> None:
    log.info("document skipped", extra={"document_id": doc.id, "source_kind": doc.source_kind, "reason": reason,
                                        **extra})
