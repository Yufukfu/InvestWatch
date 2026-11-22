"""M2 text rules R10 (language consistency) and R9 (comprehensibility), change analytics-m2-text-rules.

Kept out of `rules/m2.py` so the parallel visual-rules change does not collide there. Both rules share R3's
risk-warning detector through `_RiskWarnings` and its YAML anchors.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import replace
from functools import cached_property

from ..llm.judge import LlmVerdict
from ..models import Block, RuleResult
from ..preprocessing import Sentence, sentence_language
from .engine import Context, compile_patterns, register
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


#: The model's rating, stated at the start of its explanation as the R9 question asks ("Ocena: 2/5").
_RATING = re.compile(r"\bocena\s*:?\s*([1-5])\s*/\s*5\b", re.IGNORECASE)
_WORD = re.compile(r"\w+")


@register
class R9Comprehensibility(_RiskWarnings):
    """ZASÓB R9: "ostrzeżenie o ryzyku … językiem zrozumiałym dla przeciętnego odbiorcy grupy docelowej".

    LLM-first: the rules only raise a signal (long sentences, jargon) and never fail; the LLM decides with a 1-5
    rating, and `accept_llm_verdict` keeps a fail only for a rating of 2 or lower (a pass only for 4 or higher).
    """

    rule_id = "R9"

    @cached_property
    def _p(self) -> dict:
        p = self.spec.params
        return {
            "jargon": compile_patterns(p.get("jargon_patterns", [])),
            "max_avg": int(p.get("max_avg_sentence_words", 30)),
            "max_share": float(p.get("max_jargon_share", 0.05)),
            "min_hits": int(p.get("min_jargon_hits", 2)),
        }

    def _hits(self, text: str) -> int:
        return sum(len(j.findall(text)) for j in self._p["jargon"])

    def evaluate(self, ctx: Context) -> RuleResult:
        warnings = [s for s in ctx.pre.sentences if self.is_warning(s.text)]
        if not warnings:
            return self.result("not_applicable", None, NO_RISK_INFO)
        p = self._p
        words = sum(len(_WORD.findall(s.text)) for s in warnings)
        hits = [self._hits(s.text) for s in warnings]
        total = sum(hits)
        avg = words / len(warnings)
        share = total / words if words else 0.0
        numbers = (
            f"średnia długość zdania {avg:.0f} słów, terminy specjalistyczne: {total} "
            f"(udział {share * 100:.0f}%)".replace(".", ",")
        )
        raised = avg > p["max_avg"] or share >= p["max_share"] or total >= p["min_hits"]
        if not raised:
            return self.result("pass", warnings[0].text, f"Ostrzeżenie o ryzyku jest napisane prostym językiem ({numbers}).")
        worst = warnings[hits.index(max(hits))]
        return self.result(
            "uncertain", worst.text,
            f"Ostrzeżenie o ryzyku może być niezrozumiałe dla przeciętnego klienta ({numbers}) – do weryfikacji.",
        )

    def accept_llm_verdict(self, verdict: LlmVerdict) -> LlmVerdict:
        m = _RATING.search(verdict.explanation)
        rating = int(m.group(1)) if m else None
        if verdict.result == "fail" and rating is not None and rating <= 2:
            return verdict
        if verdict.result == "pass" and rating is not None and rating >= 4:
            return verdict
        if verdict.result in ("fail", "pass"):
            return replace(verdict, result="uncertain")
        return verdict
