"""Which modules run for a document (`.docs/analytics-plan.md` §2 step 4; design decision 5).

This change: `firm_own` -> M2. M1/M3 (third-party content) are not implemented yet, so
`third_party` and `unknown` documents get no module and the pipeline logs why.
"""

from __future__ import annotations

from ..models import Module, ScrapedDocument


def route(doc: ScrapedDocument) -> list[Module]:
    if doc.source_kind == "firm_own":
        return ["M2"]
    return []
