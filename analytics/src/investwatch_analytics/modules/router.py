"""Which module a document goes to (`.docs/analytics-plan.md` §2 step 4; change analytics-m1-m3, design 1-2).

By publisher identity and registry result, not by `source_kind` alone:
- the publisher is a registry firm (its own account or domain, on any platform) -> M2 for that firm;
- `firm_own` with a registry match by text or page host -> M2; without one -> M3 (never M2: M2 is only
  for firms registered in Poland);
- `third_party`/`unknown` mentioning a registry firm by text or link host -> M1 (the pipeline may add M3
  against the publisher); otherwise -> M3.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..models import Module, ScrapedDocument
from ..registry import DOMAIN_CONFIDENCE, NAME_CONFIDENCE, Firm, FirmMatch, Registry
from .advertiser import publisher_firm


@dataclass(frozen=True)
class Route:
    module: Module
    firm_match: FirmMatch | None


def route(doc: ScrapedDocument, registry: Registry) -> Route:
    publisher = publisher_firm(doc, registry)
    if publisher is not None:
        return Route("M2", _publisher_match(doc, registry, publisher))
    if doc.source_kind == "firm_own":
        match = registry.match(doc.text, doc.url)
        return Route("M2", match) if match is not None else Route("M3", None)
    match = registry.match(doc.text, doc.url) or registry.match_links(doc.links)
    return Route("M1", match) if match is not None else Route("M3", None)


def _publisher_match(doc: ScrapedDocument, registry: Registry, firm: Firm) -> FirmMatch:
    """The publisher firm as the M2 firm, even when the text names another firm (a depositary bank, say)."""
    match = registry.match(doc.text, doc.url)
    if match is not None and match.firm.id == firm.id:
        return match
    quote = registry.find_name(firm, doc.text)
    if quote is not None:
        return FirmMatch(firm, NAME_CONFIDENCE, "name", quote)
    return FirmMatch(firm, DOMAIN_CONFIDENCE, "domain", None)
