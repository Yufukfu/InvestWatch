"""M2 rules, rules-only versions (`.docs/analytics-plan.md` §5): R1, R2, R3."""

from __future__ import annotations

import re
from bisect import bisect_left
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

    @cached_property
    def _negation(self) -> re.Pattern | None:
        pattern = self.spec.params.get("negation_before")
        return re.compile(pattern, re.IGNORECASE) if pattern else None

    def _negated(self, text: str, m: re.Match) -> bool:
        if m.group(0).startswith("#") or self._negation is None:
            return False
        # pos/endpos, not a slice: `\b` still sees the character before the window.
        return bool(self._negation.search(text, max(0, m.start() - 40), m.start()))

    def evaluate(self, ctx: Context) -> RuleResult:
        text = ctx.doc.text
        hits = sorted(
            (m for p in self._labels for m in p.finditer(text) if not self._negated(text, m)),
            key=lambda m: m.start(),
        )
        if not hits:
            return self.result("fail", None, "Brak oznaczenia materiału jako reklamy.")
        k = int(self.spec.params.get("prominent_sentences", 2))
        sentences = ctx.pre.sentences
        edges = [s for i, s in enumerate(sentences) if i < k or i >= len(sentences) - k]

        def prominent(m: re.Match) -> bool:
            return m.group(0).startswith("#") or any(s.start <= m.start() < s.end for s in edges)

        shown = next((m for m in hits if prominent(m)), None)
        if shown is not None:
            return self.result("pass", shown.group(0), "Materiał jest oznaczony jako reklama.")
        return self.result(
            "uncertain", hits[0].group(0),
            "Oznaczenie reklamy występuje tylko w środku tekstu, bez wyeksponowania – do weryfikacji.",
        )


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
            "risk_ok": compile_patterns(p.get("risk_override_patterns", [])),
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
        warnings = [
            i for i, s in enumerate(sentences)
            if any(o.search(s.text) for o in p["risk_ok"]) or self._hits(s.text, p["risk"], p["risk_x"])
        ]
        near = [i for i in warnings if not sentences[i].text.lstrip("( ").startswith(p["footnote"])]
        # `near` is ascending (sentence order), so a claim is covered iff the first warning at or after
        # `c - window` is at most `c + window`. Comparing every claim with every warning was quadratic in the
        # sentence count ("Zysk 5%. Ryzyko straty. " x 16 000 took ~65 s; PR #26 review).
        window = p["window"]
        uncovered = [
            c for c in claims
            if (i := bisect_left(near, c - window)) == len(near) or near[i] > c + window
        ]
        if not uncovered:
            nearest = min(near, key=lambda w: abs(w - claims[0]))
            return self.result("pass", sentences[nearest].text, "Ostrzeżenie o ryzyku towarzyszy informacji o zyskach.")
        claim = sentences[uncovered[0]].text
        if warnings:
            why = "Ostrzeżenie o ryzyku jest oddalone od obietnicy zysku lub umieszczone tylko w przypisie."
        else:
            why = "Obietnica zysku bez jakiegokolwiek ostrzeżenia o ryzyku."
        return self.result("fail", claim, why)


_YEAR = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")


@register
class R14PastPerformanceDisclaimer(Rule):
    """ZASÓB R14: a clear disclaimer must be present; no proximity requirement (unlike R3).

    A footnote-only disclaimer passes: its placement is R6's ("ryzyko ukryte w przypisach").
    """

    rule_id = "R14"

    @cached_property
    def _p(self) -> dict:
        p = self.spec.params
        return {
            "figure": compile_patterns(p.get("figure_patterns", [])),
            "figure_x": compile_patterns(p.get("figure_exclude_patterns", [])),
            "past": compile_patterns(p.get("past_patterns", [])),
            "future": compile_patterns(p.get("future_patterns", [])),
            "disclaimer": compile_patterns(p.get("disclaimer_patterns", [])),
            "footnote": tuple(p.get("footnote_markers", [])),
        }

    def _is_past_performance(self, sentence: str, fetch_year: int) -> bool:
        p = self._p
        if not R3RiskNextToReturns._hits(sentence, p["figure"], p["figure_x"]):
            return False
        if any(m.search(sentence) for m in p["past"]):
            return True
        if any(f.search(sentence) for f in p["future"]):
            return False
        return any(int(y) <= fetch_year for y in _YEAR.findall(sentence))

    def evaluate(self, ctx: Context) -> RuleResult:
        p = self._p
        sentences = ctx.pre.sentences
        fetch_year = ctx.doc.fetched_at.year
        claims = [s for s in sentences if self._is_past_performance(s.text, fetch_year)]
        if not claims:
            return self.result("not_applicable", None, "Materiał nie prezentuje wyników historycznych.")
        disclaimers = [s for s in sentences if any(d.search(s.text) for d in p["disclaimer"])]
        if not disclaimers:
            return self.result(
                "fail", claims[0].text,
                "Wyniki historyczne bez wyraźnego zastrzeżenia, że nie są wiarygodnym wskaźnikiem przyszłych wyników.",
            )
        shown = [s for s in disclaimers if not s.text.lstrip("( ").startswith(p["footnote"])]
        quote = (shown or disclaimers)[0].text
        return self.result("pass", quote, "Materiał zawiera zastrzeżenie dotyczące wyników historycznych.")
