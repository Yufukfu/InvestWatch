"""M2 rules, rules-only versions (`.docs/analytics-plan.md` §5): R1, R2, R3."""

from __future__ import annotations

import re
from functools import cached_property

from ..models import RuleResult
from .engine import Context, Rule, compile_patterns, register


@register
class R1FirmIdentification(Rule):
    rule_id = "R1"

    def evaluate(self, ctx: Context) -> RuleResult:
        match = ctx.firm_match
        if match is None:
            return self.result("fail", None, "Nie zidentyfikowano w materiale firmy z rejestru KNF.")
        quote = ctx.registry.find_name(match.firm, ctx.doc.text)
        if quote is None:
            return self.result(
                "fail", None,
                f"Nazwa firmy ({match.firm.name}) nie jest podana w treści materiału.",
            )
        return self.result("pass", quote, "Nazwa firmy jest podana w materiale.")


@register
class R2AdLabel(Rule):
    rule_id = "R2"

    @cached_property
    def _labels(self) -> list[re.Pattern]:
        return [
            re.compile(r"(?<!\w)" + r"\s+".join(map(re.escape, label.split())) + r"(?!\w)", re.IGNORECASE)
            for label in self.spec.params.get("labels", [])
        ]

    def evaluate(self, ctx: Context) -> RuleResult:
        hits = [m for p in self._labels if (m := p.search(ctx.doc.text))]
        if not hits:
            return self.result("fail", None, "Brak oznaczenia materiału jako reklamy.")
        first = min(hits, key=lambda m: m.start())
        return self.result("pass", first.group(0), "Materiał jest oznaczony jako reklama.")


@register
class R3RiskNextToReturns(Rule):
    rule_id = "R3"

    @cached_property
    def _p(self) -> dict:
        p = self.spec.params
        return {
            "claim": compile_patterns(p.get("claim_patterns", [])),
            "claim_x": compile_patterns(p.get("claim_exclude_patterns", [])),
            "risk": compile_patterns(p.get("risk_patterns", [])),
            "risk_x": compile_patterns(p.get("risk_exclude_patterns", [])),
            "window": int(p.get("window", 2)),
            "footnote": tuple(p.get("footnote_markers", [])),
        }

    @staticmethod
    def _hits(text: str, include: list[re.Pattern], exclude: list[re.Pattern]) -> bool:
        for x in exclude:
            text = x.sub(" ", text)
        return any(p.search(text) for p in include)

    def evaluate(self, ctx: Context) -> RuleResult:
        p = self._p
        sentences = ctx.pre.sentences
        claims = [i for i, s in enumerate(sentences) if self._hits(s.text, p["claim"], p["claim_x"])]
        if not claims:
            return self.result("not_applicable", None, "Materiał nie zawiera obietnic zysku ani stóp zwrotu.")
        warnings = [i for i, s in enumerate(sentences) if self._hits(s.text, p["risk"], p["risk_x"])]
        near = [i for i in warnings if not sentences[i].text.startswith(p["footnote"])]
        uncovered = [c for c in claims if not any(abs(c - w) <= p["window"] for w in near)]
        if not uncovered:
            nearest = min(near, key=lambda w: abs(w - claims[0]))
            return self.result("pass", sentences[nearest].text, "Ostrzeżenie o ryzyku towarzyszy informacji o zyskach.")
        claim = sentences[uncovered[0]].text
        if warnings:
            why = "Ostrzeżenie o ryzyku jest oddalone od obietnicy zysku lub umieszczone tylko w przypisie."
        else:
            why = "Obietnica zysku bez jakiegokolwiek ostrzeżenia o ryzyku."
        return self.result("fail", claim, why)
