"""Pure pipeline: one ScrapedDocument -> zero or more Findings. No I/O, deterministic given `now` and `new_id`."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from datetime import datetime, timezone

from .models import Finding, ScrapedDocument
from .modules import m2
from .modules.router import route
from .preprocessing import preprocess
from .registry import Registry
from .rules.engine import Catalogue, Context

log = logging.getLogger(__name__)


def analyze(
    doc: ScrapedDocument,
    *,
    registry: Registry,
    catalogue: Catalogue,
    now: datetime | None = None,
    new_id: Callable[[], str] = lambda: str(uuid.uuid4()),
) -> list[Finding]:
    now = now or datetime.now(timezone.utc)
    pre = preprocess(doc.text)
    if pre.is_empty:
        log.info("document skipped", extra={"document_id": doc.id, "reason": "empty_text"})
        return []
    modules = route(doc)
    if not modules:
        log.info(
            "document skipped",
            extra={"document_id": doc.id, "source_kind": doc.source_kind, "reason": "module_not_implemented"},
        )
        return []
    ctx = Context(doc=doc, pre=pre, firm_match=registry.match(doc.text, doc.url), registry=registry)
    findings = [m2.build_finding(ctx, catalogue, now=now, new_id=new_id) for module in modules if module == "M2"]
    for f in findings:
        log.info("finding built", extra={"document_id": doc.id, "module": f.module, "score": f.score})
    return findings
