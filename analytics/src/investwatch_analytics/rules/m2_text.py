"""M2 text rules R10 (language consistency) and R9 (comprehensibility), change analytics-m2-text-rules.

Kept out of `rules/m2.py` so the parallel visual-rules change does not collide there. Both rules share R3's
risk-warning detector through `_RiskWarnings` and its YAML anchors.
"""

from __future__ import annotations

from collections import Counter

from ..models import Block, RuleResult
from ..preprocessing import Sentence, sentence_language
from .engine import Context, register
from .m2 import NO_RISK_INFO, VIEWPORTS, _RiskWarnings

#: Blocks that never set the main message's language (legal boilerplate, footers).
NON_MAIN_REGIONS = ("footer", "legal")


@register
class R10LanguageConsistency(_RiskWarnings):
    """ZASÓB R10: "informacje o ryzyku nie są podane w innym języku niż główny przekaz materiału"."""

    rule_id = "R10"

    def _main_blocks(self, blocks: list[Block]) -> list[Block]:
        present = [vp for vp in VIEWPORTS if any(b.viewport == vp for b in blocks)]
        if not present:
            return []
        viewport = present[0]  # desktop first
        return [
            b for b in blocks
            if b.viewport == viewport and b.visible and b.region not in NON_MAIN_REGIONS and not self.is_warning(b.text)
        ]

    @staticmethod
    def _majority(texts: list[str]) -> str | None:
        weights: Counter[str] = Counter()
        for text in texts:
            lang = sentence_language(text)
            if lang is not None:
                weights[lang] += len(text)
        if not weights:
            return None
        (top, w1), *rest = weights.most_common()
        return None if rest and rest[0][1] == w1 else top

    def main_language(self, ctx: Context, warnings: list[Sentence]) -> str | None:
        if ctx.doc.blocks:
            lang = self._majority([b.text for b in self._main_blocks(ctx.doc.blocks)])
            if lang is not None:
                return lang
        warning_ids = {id(s) for s in warnings}
        lang = self._majority([s.text for s in ctx.pre.sentences if id(s) not in warning_ids])
        return lang if lang is not None else ctx.pre.lang

    def evaluate(self, ctx: Context) -> RuleResult:
        warnings = [s for s in ctx.pre.sentences if self.is_warning(s.text)]
        if not warnings:
            return self.result("not_applicable", None, NO_RISK_INFO)
        main = self.main_language(ctx, warnings)
        langs = [sentence_language(s.text) for s in warnings]
        if main is not None:
            same = next((s for s, lang in zip(warnings, langs) if lang == main), None)
            if same is not None:
                return self.result("pass", same.text, f"Ostrzeżenie o ryzyku jest w języku głównego przekazu ({main}).")
        if main is None or None in langs:
            return self.result(
                "uncertain", warnings[0].text,
                "Nie udało się ustalić języka ostrzeżenia o ryzyku lub głównego przekazu – do weryfikacji.",
            )
        return self.result(
            "fail", warnings[0].text,
            f"Ostrzeżenie o ryzyku jest w innym języku ({langs[0]}) niż główny przekaz materiału ({main}).",
        )
