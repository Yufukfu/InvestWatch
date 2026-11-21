"""`content_excerpt` for M1/M3: the passage that triggered the finding, not the start of the page (#35 review)."""

from __future__ import annotations

from ..models import RuleResult
from ..preprocessing import Preprocessed, normalize

EXCERPT_MAX = 500
#: Context kept before the first evidence, so the excerpt reads as a passage rather than starting mid-quote.
LEAD = EXCERPT_MAX // 4


def excerpt(text: str, pre: Preprocessed, rules: list[RuleResult]) -> str | None:
    """At most EXCERPT_MAX characters around the earliest evidence found in `text`; the start without one.

    Only quotes from `text` count (a handle or a link quoted from metadata has no position in the text).
    """
    positions = [p for r in rules if r.evidence and r.result in ("fail", "uncertain") and (p := text.find(r.evidence)) >= 0]
    if not positions:
        return pre.normalized[:EXCERPT_MAX] or None
    start = max(0, min(positions) - LEAD)
    # Twice the limit of raw text, so collapsing whitespace still leaves a full window.
    return normalize(text[start:start + 2 * EXCERPT_MAX])[:EXCERPT_MAX] or None
