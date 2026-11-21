"""M2 rules, rules-only versions (`.docs/analytics-plan.md` §5): R1, R2, R3."""

from __future__ import annotations

import re
from bisect import bisect_left
from functools import cached_property

from ..models import Block, EvidenceLocator, RuleResult
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


# A year only in a year context ("w 2025", "za 2024 r.", "2023 roku"), so amounts ("2000 zł") and
# dates ("do 31.12.2026") are not years; an amount after a preposition ("od 2000 zł") is not either.
_YEAR = re.compile(
    r"\b(?:w|we|za|od|z)\s+(?:roku\s+)?((?:19|20)\d{2})(?!\d)(?!\s*(?:zł|pln|eur|usd|€|\$|tys))|(?<![\d.])((?:19|20)\d{2})\s*(?:r\.|rok\w*)",
    re.IGNORECASE,
)


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
            "figure_x": compile_patterns(p.get("figure_exclude_patterns", []) + p.get("figure_extra_exclude_patterns", [])),
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
        return any(int(a or b) <= fetch_year for a, b in _YEAR.findall(sentence))

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


# ---- visual rules (blocks) ---------------------------------------------------------------------

VIEWPORTS = ("desktop", "mobile", "tablet")
_SEVERITY_ORDER = {"fail": 3, "uncertain": 2, "pass": 1}
NO_BLOCKS = "Brak danych o renderowaniu strony – reguła wizualna nie dotyczy."
NO_RISK_INFO = "Brak informacji o ryzyku w materiale – reguła nie dotyczy (brak ostrzeżenia ocenia R3)."
NO_RISK_BLOCK = "Brak informacji o ryzyku w danych renderowania – reguła nie dotyczy."


def locate(text: str, needle: str) -> str | None:
    """`needle` as it appears in `text`: exact, else whitespace-insensitive; None when absent."""
    needle = needle.strip()
    if not needle:
        return None
    if needle in text:
        return needle
    m = re.search(r"\s+".join(map(re.escape, needle.split())), text)
    return m.group(0) if m else None


def locator_for(b: Block) -> EvidenceLocator:
    bbox = b.bbox if b.bbox is not None and len(b.bbox) == 4 else None
    return EvidenceLocator(viewport=b.viewport, bbox=bbox)


class _RiskWarnings(Rule):
    """Shared by the rules that presuppose risk information (R4, R6): R3's warning dictionary via YAML anchors."""

    @cached_property
    def _risk(self) -> dict:
        p = self.spec.params
        return {
            "risk": compile_patterns(p.get("risk_patterns", [])),
            "risk_x": compile_patterns(p.get("risk_exclude_patterns", [])),
            "risk_ok": compile_patterns(p.get("risk_override_patterns", [])),
            "disclaimer": compile_patterns(p.get("disclaimer_patterns", [])),
            "footnote": tuple(p.get("footnote_markers", [])),
        }

    def is_warning(self, text: str) -> bool:
        r = self._risk
        return (
            any(o.search(text) for o in r["risk_ok"])
            or any(d.search(text) for d in r["disclaimer"])
            or R3RiskNextToReturns._hits(text, r["risk"], r["risk_x"])
        )

    def is_footnote(self, text: str) -> bool:
        return text.lstrip("( ").startswith(self._risk["footnote"])

    def warning_quote(self, ctx: Context, b: Block) -> str | None:
        """The first warning sentence inside the block as it appears in the text, else the located block text."""
        span = locate(ctx.doc.text, b.text)
        if span is None:
            return None
        start = ctx.doc.text.find(span)
        end = start + len(span)
        inside = (s for s in ctx.pre.sentences if s.start >= start and s.end <= end and self.is_warning(s.text))
        first = next(inside, None)
        return first.text if first is not None else span

    def no_risk_result(self, ctx: Context) -> RuleResult:
        """not_applicable when there is no risk block; R3 carries a missing warning (ZASÓB, counted once)."""
        in_text = any(self.is_warning(s.text) for s in ctx.pre.sentences)
        return self.result("not_applicable", None, NO_RISK_BLOCK if in_text else NO_RISK_INFO)


@register
class R6HiddenRisk(_RiskWarnings):
    """ZASÓB R6 "ryzyko ukryte w przypisach": risk only in footer / legal / footnotes, not in view on load."""

    rule_id = "R6"

    def _placement_hidden(self, b: Block) -> bool:
        regions = self.spec.params.get("hiding_regions", ["footer", "legal"])
        return b.region in regions or self.is_footnote(b.text)

    def _state(self, b: Block) -> str:
        if not self._placement_hidden(b) or b.in_viewport_on_load is True:
            return "pass"
        return "fail" if b.in_viewport_on_load is False else "uncertain"

    def _viewport(self, blocks: list[Block]) -> tuple[str, Block]:
        """pass if any risk block is exposed; else uncertain if any position is unknown; else fail."""
        states = [(self._state(b), b) for b in blocks]
        for wanted in ("pass", "uncertain", "fail"):
            hit = next((b for st, b in states if st == wanted), None)
            if hit is not None:
                return wanted, hit
        raise AssertionError("unreachable: blocks is non-empty")

    def evaluate(self, ctx: Context) -> RuleResult:
        if not ctx.doc.blocks:
            return self.result("not_applicable", None, NO_BLOCKS)
        verdicts = []
        for vp in VIEWPORTS:
            risk = [b for b in ctx.doc.blocks if b.viewport == vp and self.is_warning(b.text)]
            if risk:
                verdicts.append(self._viewport(risk))
        if not verdicts:
            return self.no_risk_result(ctx)
        result, b = max(verdicts, key=lambda v: _SEVERITY_ORDER[v[0]])  # first (desktop-first) wins ties
        why = {
            "fail": f"Ostrzeżenie o ryzyku tylko w stopce, sekcji prawnej lub przypisie i niewidoczne bez przewijania ({b.viewport}).",
            "uncertain": f"Ostrzeżenie o ryzyku w stopce, sekcji prawnej lub przypisie; brak danych, czy jest widoczne bez przewijania ({b.viewport}).",
            "pass": "Ostrzeżenie o ryzyku jest wyeksponowane poza stopką i przypisami lub widoczne bez przewijania.",
        }[result]
        return self.result(result, self.warning_quote(ctx, b), why, locator_for(b))


def weighted_median(values: list[tuple[float, float]]) -> float:
    """Lower weighted median of (value, weight) pairs: the first value whose cumulative weight reaches half."""
    ordered = sorted(values)
    half = sum(w for _, w in ordered) / 2
    acc = 0.0
    for value, weight in ordered:
        acc += weight
        if acc >= half:
            return value
    return ordered[-1][0]


def _pl(x: float) -> str:
    return f"{x:.2f}".replace(".", ",")


def _px(x: float) -> str:
    return f"{x:g}".replace(".", ",")


@register
class R4RiskFontSize(_RiskWarnings):
    """ZASÓB R4: the risk font vs "przeważająca wielkość czcionki materiału" (the dominant size).

    Dominant size = length-weighted median `font_size_px` of the visible blocks of a viewport; the task text
    asks for a warning "proporcjonalny do informacji o zyskach oraz wyraźny". `min_ratio` is our threshold.
    """

    rule_id = "R4"

    def evaluate(self, ctx: Context) -> RuleResult:
        if not ctx.doc.blocks:
            return self.result("not_applicable", None, NO_BLOCKS)
        min_ratio = float(self.spec.params.get("min_ratio", 0.75))
        measured = []  # (ratio, risk block, dominant size)
        any_risk_block = False
        for vp in VIEWPORTS:
            blocks = [b for b in ctx.doc.blocks if b.viewport == vp]
            any_risk_block |= any(self.is_warning(b.text) for b in blocks)
            visible = [b for b in blocks if b.visible]
            risk = [b for b in visible if self.is_warning(b.text)]
            if not risk:
                continue
            dominant = weighted_median([(b.font_size_px, len(b.text)) for b in visible])
            largest = max(risk, key=lambda b: b.font_size_px)
            measured.append((largest.font_size_px / dominant if dominant else 1.0, largest, dominant))
        if not measured:
            if any_risk_block:
                return self.result(
                    "not_applicable", None,
                    "Ostrzeżenie o ryzyku nie jest widoczne na stronie – widoczność ocenia R5.",
                )
            return self.no_risk_result(ctx)
        ratio, b, dominant = min(measured, key=lambda m: m[0])  # worst viewport; desktop first on ties
        sizes = f"{_px(b.font_size_px)} px przy przeważającej czcionce {_px(dominant)} px ({_pl(ratio)}×, {b.viewport})"
        if ratio < min_ratio:
            return self.result(
                "fail", self.warning_quote(ctx, b),
                f"Ostrzeżenie o ryzyku zbyt małą czcionką: {sizes}; wymagane co najmniej {_pl(min_ratio)}×.",
                locator_for(b),
            )
        return self.result(
            "pass", self.warning_quote(ctx, b),
            f"Czcionka ostrzeżenia proporcjonalna do treści: {sizes}.", locator_for(b),
        )


# ---- supervisor mentions (R17, R18) ------------------------------------------------------------


class _SupervisorMention(Rule):
    """Detect a supervisor mention first, then classify how it is used (ZASÓB R17 / R18)."""

    @cached_property
    def _supervisor(self) -> list[re.Pattern]:
        return compile_patterns(self.spec.params.get("supervisor_patterns", []))

    def mentions(self, ctx: Context) -> list[int]:
        return [i for i, s in enumerate(ctx.pre.sentences) if any(p.search(s.text) for p in self._supervisor)]


@register
class R17SupervisoryApproval(_SupervisorMention):
    rule_id = "R17"

    @cached_property
    def _approval(self) -> list[re.Pattern]:
        return compile_patterns(self.spec.params.get("approval_patterns", []))

    def evaluate(self, ctx: Context) -> RuleResult:
        sentences = ctx.pre.sentences
        idx = self.mentions(ctx)
        if not idx:
            return self.result("not_applicable", None, "Materiał nie odwołuje się do organu nadzoru.")
        approving = next((i for i in idx if any(p.search(sentences[i].text) for p in self._approval)), None)
        if approving is not None:
            return self.result(
                "fail", sentences[approving].text,
                "Odwołanie do organu nadzoru sugeruje zatwierdzenie lub aprobatę produktu.",
            )
        return self.result(
            "pass", sentences[idx[0]].text,
            "Odwołanie do nadzoru bez słów sugerujących aprobatę produktu (samo stwierdzenie nadzoru nie jest naruszeniem).",
        )


@register
class R18SupervisionAsSafety(_SupervisorMention):
    rule_id = "R18"

    @cached_property
    def _safety(self) -> list[re.Pattern]:
        return compile_patterns(self.spec.params.get("safety_patterns", []))

    def _safe(self, text: str) -> bool:
        return any(p.search(text) for p in self._safety)

    def evaluate(self, ctx: Context) -> RuleResult:
        sentences = ctx.pre.sentences
        idx = self.mentions(ctx)
        if not idx:
            return self.result("not_applicable", None, "Materiał nie odwołuje się do organu nadzoru.")
        same = next((i for i in idx if self._safe(sentences[i].text)), None)
        if same is not None:
            return self.result(
                "fail", sentences[same].text,
                "Nadzór jest użyty jako argument bezpieczeństwa inwestycji w tym samym zdaniu.",
            )
        window = int(self.spec.params.get("window", 1))
        near = next(
            (i for i in idx
             if any(self._safe(sentences[j].text)
                    for j in range(max(0, i - window), min(len(sentences), i + window + 1)) if j != i)),
            None,
        )
        if near is not None:
            return self.result(
                "uncertain", sentences[near].text,
                "Odwołanie do nadzoru sąsiaduje z zapewnieniem o bezpieczeństwie – do weryfikacji.",
            )
        return self.result("pass", sentences[idx[0]].text, "Nadzór nie jest użyty jako argument bezpieczeństwa.")
