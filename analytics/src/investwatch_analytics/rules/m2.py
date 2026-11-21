"""M2 rules, rules-only versions (`.docs/analytics-plan.md` §5): R1, R2, R3."""

from __future__ import annotations

import math
import re
from bisect import bisect_left
from dataclasses import dataclass
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
        # ZASÓB R1 checks the official name; a former or trade name identifies the firm only loosely.
        if official := ctx.registry.find_official_name(match.firm, ctx.doc.text):
            return self.result("pass", official, "Nazwa firmy jest podana w materiale.")
        if alias := ctx.registry.find_name(match.firm, ctx.doc.text):
            return self.result(
                "uncertain", alias,
                f"W materiale użyto nazwy nieoficjalnej/dawnej: „{alias}”; oficjalna nazwa: {match.firm.name}.",
            )
        return self.result(
            "fail", None,
            f"Nazwa firmy ({match.firm.name}) nie jest podana w treści materiału.",
        )


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
            "margin": int(p.get("borderline_margin", 2)),
            "footnote": tuple(p.get("footnote_markers", [])),
        }

    _borderline = False  # set by evaluate() for this document; read by ask_llm() (one instance per run)

    def ask_llm(self, ctx: Context, result: RuleResult) -> bool:
        """Only the near-window proximity case (ZASÓB: the warning "bezpośrednio towarzyszy" the claim).

        Never an absent warning, a footnote-only one, one farther than `borderline_margin`, or a claim matched by
        vocabulary only (ADR 0309).
        """
        return self._borderline and result.result == "fail" and self.spec.llm is not None

    def _is_borderline(self, sentences, uncovered: list[int], near: list[int]) -> bool:
        p = self._p
        if not near:
            return False
        for c in uncovered:
            distance = min(abs(c - w) for w in near)
            if distance > p["window"] + p["margin"]:  # uncovered, so already farther than `window`
                return False
            if not any(pat.search(sentences[c].text) for pat in p["claim"][:1]):  # a percent figure, not vocabulary
                return False
        return True

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
        self._borderline = self._is_borderline(sentences, uncovered, near)
        claim = sentences[uncovered[0]].text
        if warnings:
            why = "Ostrzeżenie o ryzyku jest oddalone od obietnicy zysku lub umieszczone tylko w przypisie."
        else:
            why = "Obietnica zysku bez jakiegokolwiek ostrzeżenia o ryzyku."
        return self.result("fail", claim, why)


# A year only in a year context ("w 2025", "za 2024 r.", "2023 roku"), so amounts ("2000 zł") and
# dates ("do 31.12.2026") are not years; an amount after a preposition ("od 2000 zł") is not either.
def _one_of(patterns: list[str]) -> list[re.Pattern]:
    """The patterns as one case-insensitive alternation (empty list: no pattern, never matches)."""
    return [re.compile("|".join(f"(?:{x})" for x in patterns), re.IGNORECASE)] if patterns else []


def _hits_fast(text: str, include: list[re.Pattern], exclude: list[re.Pattern]) -> bool:
    """`R3RiskNextToReturns._hits` with a cheap pre-check: no include match in the raw text means none after the
    exclusions either (an exclusion only blanks text out). Used by R14, R17 and R18, whose include patterns cannot
    be completed by a blanked-out gap; R3 keeps the plain version."""
    if not any(p.search(text) for p in include):
        return False
    return R3RiskNextToReturns._hits(text, include, exclude)


_YEAR = re.compile(
    r"\b(?:w|we|za|od|z)\s+(?:roku\s+)?((?:19|20)\d{2})(?!\d)(?!\s*(?:zł|pln|eur|usd|€|\$|tys(?:\.|\b)))|(?<![\d.])((?:19|20)\d{2})\s*(?:r\.|rok\w*)",
    re.IGNORECASE,
)


NO_PAST_PERFORMANCE = "Materiał nie prezentuje wyników historycznych."


class _PastPerformance(Rule):
    """One past-performance detector for R12a, R12b and R14 (ADR 0315: they never disagree on the trigger).

    A sentence presents past performance with a past marker (or a year <= the fetch year and no future marker)
    and a return figure: a percentage that is not a fee or tax, or an amount next to return vocabulary. The
    parameter lists are YAML anchors on R14 (`pp_*`), aliased in R12a and R12b.
    """

    @cached_property
    def _pp(self) -> dict:
        p = self.spec.params
        return {
            "figure": compile_patterns(p.get("figure_patterns", [])),
            "figure_x": compile_patterns(p.get("figure_exclude_patterns", []) + p.get("figure_extra_exclude_patterns", [])),
            # One alternation per list: one search per sentence instead of one per pattern (timing, test_redos).
            "amount": _one_of(p.get("amount_patterns", [])),
            "amount_return": _one_of(p.get("amount_return_patterns", [])),
            "past": _one_of(p.get("past_patterns", [])),
            "future": _one_of(p.get("future_patterns", [])),
        }

    def is_past_performance(self, sentence: str, fetch_year: int) -> bool:
        """A return figure AND a past marker. The marker is checked first: it is cheap, while the figure check
        runs every exclusion over the sentence (adversarial-input timing, tests/test_redos.py)."""
        p = self._pp
        if any(m.search(sentence) for m in p["past"]):
            past = True
        elif any(f.search(sentence) for f in p["future"]):
            return False
        else:
            past = any(int(a or b) <= fetch_year for a, b in _YEAR.findall(sentence))
        if not past:
            return False
        if _hits_fast(sentence, p["figure"], p["figure_x"]):
            return True
        # Past results in any unit: an amount counts only next to return vocabulary ("zarobili 5 000 zł").
        return any(a.search(sentence) for a in p["amount"]) and any(r.search(sentence) for r in p["amount_return"])

    def past_performance(self, ctx: Context) -> list:
        """The past-performance sentences of the document, in order."""
        fetch_year = ctx.doc.fetched_at.year
        return [s for s in ctx.pre.sentences if self.is_past_performance(s.text, fetch_year)]


@register
class R14PastPerformanceDisclaimer(_PastPerformance):
    """ZASÓB R14: a clear disclaimer must be present; no proximity requirement (unlike R3).

    A footnote-only disclaimer passes: its placement is R6's ("ryzyko ukryte w przypisach").
    """

    rule_id = "R14"

    @cached_property
    def _p(self) -> dict:
        p = self.spec.params
        return {
            "disclaimer": compile_patterns(p.get("disclaimer_patterns", [])),
            "footnote": tuple(p.get("footnote_markers", [])),
        }

    def evaluate(self, ctx: Context) -> RuleResult:
        p = self._p
        sentences = ctx.pre.sentences
        claims = self.past_performance(ctx)
        if not claims:
            return self.result("not_applicable", None, NO_PAST_PERFORMANCE)
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
NO_RENDER_METADATA = "Brak metadanych renderowania (region, widoczność bez przewijania) – reguła nie dotyczy."


LOCATE_FUZZY_MAX = 2000  # chars; longer block texts are matched exactly only


def locate(text: str, needle: str) -> str | None:
    """`needle` as it appears in `text`: exact, else whitespace-insensitive; None when absent."""
    needle = needle.strip()
    if not needle:
        return None
    if needle in text:
        return needle
    if len(needle) > LOCATE_FUZZY_MAX:
        return None  # the whitespace-insensitive search is O(len(text) * len(needle))
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
        if b.in_viewport_on_load is True:
            return "pass"
        if b.region is None and not self.is_footnote(b.text):
            return "unknown"  # no rendering metadata: never a pass on missing data
        if not self._placement_hidden(b):
            return "pass"
        return "fail" if b.in_viewport_on_load is False else "uncertain"

    def _viewport(self, blocks: list[Block]) -> tuple[str, Block] | None:
        """pass if any risk block is exposed; uncertain if a position is unknown or metadata is partly missing;
        fail if every block is hidden; None (no verdict) when no block has rendering metadata."""
        states = [(self._state(b), b) for b in blocks]
        found = {st: next(b for s, b in states if s == st) for st in dict.fromkeys(st for st, _ in states)}
        if "pass" in found:
            return "pass", found["pass"]
        if "uncertain" in found:
            return "uncertain", found["uncertain"]
        if "fail" in found:
            return ("uncertain", found["unknown"]) if "unknown" in found else ("fail", found["fail"])
        return None

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
        verdicts = [v for v in verdicts if v is not None]
        if not verdicts:
            return self.result("not_applicable", None, NO_RENDER_METADATA)
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
    """Ratio for display, truncated (never rounded up) to 3 decimals so it cannot contradict the verdict."""
    return f"{math.floor(x * 1000) / 1000:.3f}".replace(".", ",")


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
        unmeasurable = False
        for vp in VIEWPORTS:
            blocks = [b for b in ctx.doc.blocks if b.viewport == vp]
            any_risk_block |= any(self.is_warning(b.text) for b in blocks)
            unmeasurable |= any(b.visible and b.font_size_px <= 0 and self.is_warning(b.text) for b in blocks)
            # A 0 px (or negative) block carries no readable text: it never sets the dominant size.
            visible = [b for b in blocks if b.visible and b.font_size_px > 0]
            risk = [b for b in visible if self.is_warning(b.text)]
            if not risk:
                continue
            dominant = weighted_median([(b.font_size_px, len(b.text)) for b in visible])
            largest = max(risk, key=lambda b: b.font_size_px)
            measured.append((largest.font_size_px / dominant if dominant else 1.0, largest, dominant))
        if not measured:
            if unmeasurable:
                return self.result(
                    "uncertain", None,
                    "Ostrzeżenie o ryzyku ma nieczytelny rozmiar czcionki (0 px) w danych renderowania – do weryfikacji.",
                )
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
    def _supervisor(self) -> tuple[list[re.Pattern], list[re.Pattern]]:
        p = self.spec.params
        return _one_of(p.get("supervisor_patterns", [])), compile_patterns(p.get("supervisor_exclude_patterns", []))

    def mentions(self, ctx: Context) -> list[int]:
        inc, exc = self._supervisor
        return [i for i, s in enumerate(ctx.pre.sentences) if _hits_fast(s.text, inc, exc)]


@register
class R17SupervisoryApproval(_SupervisorMention):
    rule_id = "R17"

    def ask_llm(self, ctx: Context, result: RuleResult) -> bool:
        # `when: always`, except a deterministic approval-word fail, which the LLM never sees (ADR 0309).
        return super().ask_llm(ctx, result) and result.result == "pass"

    @cached_property
    def _approval(self) -> tuple[list[re.Pattern], list[re.Pattern]]:
        p = self.spec.params
        return _one_of(p.get("approval_patterns", [])), compile_patterns(p.get("approval_exclude_patterns", []))

    def evaluate(self, ctx: Context) -> RuleResult:
        sentences = ctx.pre.sentences
        idx = self.mentions(ctx)
        if not idx:
            return self.result("not_applicable", None, "Materiał nie odwołuje się do organu nadzoru.")
        approving = next((i for i in idx if _hits_fast(sentences[i].text, *self._approval)), None)
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
    def _safety(self) -> tuple[list[re.Pattern], list[re.Pattern]]:
        p = self.spec.params
        return _one_of(p.get("safety_patterns", [])), compile_patterns(p.get("safety_exclude_patterns", []))

    def _safe(self, text: str) -> bool:
        return _hits_fast(text, *self._safety)

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


# ---- tax information (R16, analytics-m2-p1-rules) ------------------------------------------------


@register
class R16TaxInformation(Rule):
    """ZASÓB R16 (art. 44 ust. 7): tax treatment "zależy od indywidualnej sytuacji klienta" and "może ulec zmianie".

    The change part counts only where it is about tax: in the sentence of the individual part, or in a sentence
    with a tax word or `przepis…` ("Oferta może ulec zmianie" does not). Disclaimer sentences are not a tax
    reference, so a lone disclaimer is not_applicable (design §7).
    """

    rule_id = "R16"

    @cached_property
    def _p(self) -> dict:
        p = self.spec.params
        return {
            "tax": compile_patterns(p.get("tax_patterns", [])),
            "tax_x": compile_patterns(p.get("tax_exclude_patterns", [])),
            "individual": compile_patterns(p.get("tax_individual_patterns", [])),
            "change": compile_patterns(p.get("tax_change_patterns", [])),
            "context": compile_patterns(p.get("tax_context_patterns", [])),
            "subject": compile_patterns(p.get("tax_subject_patterns", [])),
        }

    def evaluate(self, ctx: Context) -> RuleResult:
        p = self._p
        texts = [s.text for s in ctx.pre.sentences]
        individual = [i for i, t in enumerate(texts) if any(x.search(t) for x in p["individual"])]
        change = [
            i for i, t in enumerate(texts)
            if any(c.search(t) for c in p["change"]) and (i in individual or any(c.search(t) for c in p["context"]))
        ]
        disclaimer = set(individual) | set(change)
        # A disclaimer sentence is a tax reference only through what is left once the disclaimer is stripped
        # ("W IKE nie płacisz podatku Belki, choć przepisy mogą ulec zmianie" is both; group 2 review).
        stripped = p["individual"] + p["change"] + p["subject"]
        refs = [
            i for i, t in enumerate(texts)
            if R3RiskNextToReturns._hits(t, p["tax"], p["tax_x"] + (stripped if i in disclaimer else []))
        ]
        if not refs:
            return self.result("not_applicable", None, "Materiał nie odwołuje się do traktowania podatkowego.")
        if individual and change:
            return self.result(
                "pass", texts[individual[0]],
                "Informacja podatkowa z zastrzeżeniem, że traktowanie podatkowe zależy od indywidualnej sytuacji "
                "klienta i może ulec zmianie.",
            )
        missing = []
        if not individual:
            missing.append("zależy od indywidualnej sytuacji klienta")
        if not change:
            missing.append("może ulec zmianie")
        quote = texts[(individual or change or refs)[0]]
        return self.result(
            "fail", quote,
            f"Informacja o traktowaniu podatkowym bez pełnego zastrzeżenia – brak informacji, że traktowanie "
            f"podatkowe {' i '.join(missing)}.",
        )


# ---- forecasts (R15, analytics-m2-p1-rules) -----------------------------------------------------


@register
class R15Forecasts(Rule):
    """ZASÓB R15 (art. 44 ust. 6): a forecast needs a warning that it is not a reliable indicator of future results.

    Every detected forecast is reported (ADR 0315): a compliant forecast is a pass quoting the forecast, with an
    explanation that starts with `Wykryto prognozę`. Warning sentences never trigger the rule (design §6).
    """

    rule_id = "R15"

    @cached_property
    def _p(self) -> dict:
        p = self.spec.params
        return {
            "performance": compile_patterns(p.get("performance_patterns", [])),
            "strong": compile_patterns(p.get("forecast_patterns", [])),
            "verb": compile_patterns(p.get("forecast_verb_patterns", [])),
            "weak": compile_patterns(p.get("forecast_weak_patterns", [])),
            "exclude": compile_patterns(p.get("forecast_exclude_patterns", []) + p.get("figure_exclude_patterns", [])),
            "figure": compile_patterns(p.get("figure_patterns", []) + p.get("amount_patterns", [])),
            "warning": compile_patterns(p.get("forecast_disclaimer_patterns", [])),
        }

    def _kind(self, sentence: str, fetch_year: int) -> str | None:
        """`forecast`, `candidate` (weak marker, no figure) or None."""
        p = self._p
        for x in p["exclude"]:
            sentence = x.sub(" ", sentence)
        figure = any(f.search(sentence) for f in p["figure"])
        results = figure or any(v.search(sentence) for v in p["performance"])
        if not results:
            return None
        strong = (
            any(s.search(sentence) for s in p["strong"])
            or any(int(a or b) > fetch_year for a, b in _YEAR.findall(sentence))
            or (figure and any(v.search(sentence) for v in p["verb"]))
        )
        weak = any(w.search(sentence) for w in p["weak"])
        if strong or (weak and figure):
            return "forecast"
        return "candidate" if weak else None

    def evaluate(self, ctx: Context) -> RuleResult:
        p = self._p
        fetch_year = ctx.doc.fetched_at.year
        warnings, forecasts, candidates = [], [], []
        for s in ctx.pre.sentences:
            if any(w.search(s.text) for w in p["warning"]):
                warnings.append(s.text)
                continue
            kind = self._kind(s.text, fetch_year)
            if kind == "forecast":
                forecasts.append(s.text)
            elif kind == "candidate":
                candidates.append(s.text)
        if not forecasts and not candidates:
            return self.result("not_applicable", None, "Materiał nie zawiera prognoz przyszłych wyników.")
        if warnings:
            quote = (forecasts or candidates)[0]
            return self.result(
                "pass", quote,
                f"Wykryto prognozę przyszłych wyników; materiał zawiera ostrzeżenie: „{warnings[0]}”.",
            )
        if forecasts:
            return self.result(
                "fail", forecasts[0],
                "Prognoza przyszłych wyników bez ostrzeżenia, że prognozy nie są wiarygodnym wskaźnikiem przyszłych wyników.",
            )
        return self.result(
            "uncertain", candidates[0],
            "Zdanie może zapowiadać przyszłe wyniki (bez liczby), a materiał nie zawiera ostrzeżenia dotyczącego "
            "prognoz – do weryfikacji.",
        )


# ---- past performance: period and scope (R12a), currency and costs (R12b) ----------------------

# N months: sub-annual unless N is a multiple of 12 ("12 miesięcy", "24 miesiące" are full periods).
_MONTHS = re.compile(r"(?<!\d)(\d{1,3})\s{0,3}-?\s{0,3}miesi\w*", re.IGNORECASE)
_YEAR_RANGE = re.compile(r"(?<!\d)((?:19|20)\d{2})\s*[-–—]\s*((?:19|20)\d{2})(?!\d)")
_LAST_N_YEARS = re.compile(r"\b(?:ostatni|minion|poprzedni)\w*\s+(\d{1,2})\s+lat\w*|\blast\s+(\d{1,2})\s+years\b", re.IGNORECASE)
_LAST_N = re.compile(r"\b(?:ostatni|minion|poprzedni)\w*\s+\d{1,3}\s+(?:lat|miesi|rok|kwarta)\w*|\blast\s+\d{1,3}\s+(?:years|months)\b", re.IGNORECASE)
_DATE = re.compile(r"(?<!\d)\d{1,2}[./]\d{1,2}[./](?:19|20)\d{2}(?!\d)")

_SUB_STATUS = {"fail": "niespełniony", "uncertain": "do weryfikacji"}
_WORST = {"fail": 2, "uncertain": 1, "pass": 0}


@dataclass(frozen=True)
class SubCheck:
    name: str
    status: str  # pass | fail | uncertain
    detail: str
    sentence: str | None = None  # the sentence that decided a fail or uncertain, if any


@register
class R12aPeriodAndScope(_PastPerformance):
    """ZASÓB R12a (art. 44 ust. 4): the last 5 years, full 12-month periods, a reference period and a source.

    Three named sub-checks; the result is the worst one and the explanation names every sub-check that is not
    `pass`, in a fixed order (design §4). The source markers are shared with R11 (`&source_markers`).
    """

    rule_id = "R12a"
    FIVE_YEARS, REFERENCE, SOURCE = "5 lat / 12 mies.", "okres referencyjny", "źródło"

    @cached_property
    def _p(self) -> dict:
        p = self.spec.params
        return {
            "short": compile_patterns(p.get("short_period_patterns", [])),
            "five": compile_patterns(p.get("five_year_patterns", [])),
            "inception": compile_patterns(p.get("inception_patterns", [])),
            "source": compile_patterns(p.get("source_patterns", [])),
        }

    def _short(self, text: str) -> bool:
        if any(s.search(text) for s in self._p["short"]):
            return True
        return any(int(n) % 12 for n in _MONTHS.findall(text))

    def _five_years(self, claims: list[str], fetch_year: int) -> bool:
        years: set[int] = set()
        for text in claims:
            if any(f.search(text) for f in self._p["five"]):
                return True
            if any(int(a or b) >= 5 for a, b in _LAST_N_YEARS.findall(text)):
                return True
            for start, end in _YEAR_RANGE.findall(text):
                if int(end) - int(start) + 1 >= 5:
                    return True
            years |= {int(a or b) for a, b in _YEAR.findall(text) if int(a or b) <= fetch_year}
        return len(years) >= 5

    @staticmethod
    def _dated(text: str) -> bool:
        return bool(_YEAR.search(text) or _YEAR_RANGE.search(text) or _DATE.search(text) or _LAST_N.search(text))

    def sub_checks(self, ctx: Context, claims: list[str]) -> list[SubCheck]:
        p = self._p
        fetch_year = ctx.doc.fetched_at.year
        short = next((t for t in claims if self._short(t)), None)
        inception = next((t for t in claims if any(i.search(t) for i in p["inception"])), None)
        if short is not None:
            five = SubCheck(self.FIVE_YEARS, "fail", "wynik za okres krótszy niż pełne 12 miesięcy", short)
        elif self._five_years(claims, fetch_year):
            five = SubCheck(self.FIVE_YEARS, "pass", "")
        elif inception is not None:
            five = SubCheck(
                self.FIVE_YEARS, "uncertain",
                "wyniki od początku działalności – dopuszczalne tylko dla produktu istniejącego krócej niż 5 lat "
                "(art. 44 ust. 4 lit. b)", inception,
            )
        else:
            five = SubCheck(self.FIVE_YEARS, "fail", "brak wyników za ostatnie 5 lat w pełnych okresach 12-miesięcznych")
        if any(self._dated(t) for t in claims):
            reference = SubCheck(self.REFERENCE, "pass", "")
        else:
            reference = SubCheck(self.REFERENCE, "fail", "nie wskazano okresu, którego dotyczą wyniki")
        if any(s.search(ctx.doc.text) for s in p["source"]):
            source = SubCheck(self.SOURCE, "pass", "")
        else:
            source = SubCheck(self.SOURCE, "fail", "nie wskazano źródła danych o wynikach")
        return [five, reference, source]

    def evaluate(self, ctx: Context) -> RuleResult:
        claims = [s.text for s in self.past_performance(ctx)]
        if not claims:
            return self.result("not_applicable", None, NO_PAST_PERFORMANCE)
        checks = self.sub_checks(ctx, claims)
        worst = max(checks, key=lambda c: _WORST[c.status]).status
        if worst == "pass":
            return self.result(
                "pass", claims[0],
                "Wyniki historyczne za ostatnie 5 lat w pełnych okresach 12-miesięcznych, ze wskazanym okresem "
                "referencyjnym i źródłem.",
            )
        open_checks = [c for c in checks if c.status != "pass"]
        decisive = next((c.sentence for c in open_checks if c.status == worst and c.sentence), None)
        listed = "; ".join(f"{c.name}: {_SUB_STATUS[c.status]} ({c.detail})" for c in open_checks)
        return self.result(worst, decisive or claims[0], f"Wyniki historyczne – {listed}.")


_DENOMINATED = re.compile(r"\b(?:denominowan\w*|denominated)\b", re.IGNORECASE)


@register
class R12bCurrencyAndCosts(_PastPerformance):
    """ZASÓB R12b (art. 44 ust. 4): the impact of fees always; a currency warning for non-PLN results only.

    ZASÓB states the currency warning without a condition; art. 44 ust. 4 lit. e requires it only for a
    currency other than the client's (PLN), so every explanation cites lit. e (Damian, design §5). Rules-only.
    """

    rule_id = "R12b"
    LIT_E = "art. 44 ust. 4 lit. e"

    @cached_property
    def _p(self) -> dict:
        p = self.spec.params
        return {
            "fee": compile_patterns(p.get("fee_patterns", [])),
            "currency": compile_patterns(p.get("foreign_currency_patterns", [])),
            "warning": compile_patterns(p.get("currency_warning_patterns", [])),
        }

    def _foreign(self, text: str) -> bool:
        return any(c.search(text) for c in self._p["currency"])

    def evaluate(self, ctx: Context) -> RuleResult:
        p = self._p
        claims = [s.text for s in self.past_performance(ctx)]
        if not claims:
            return self.result("not_applicable", None, NO_PAST_PERFORMANCE)
        text = ctx.doc.text
        foreign = next((t for t in claims if self._foreign(t)), None)
        if foreign is None:  # the product itself is denominated in a foreign currency
            foreign = next((s.text for s in ctx.pre.sentences if _DENOMINATED.search(s.text) and self._foreign(s.text)), None)
        fees = any(f.search(text) for f in p["fee"])
        warned = any(w.search(text) for w in p["warning"])
        missing = []
        if not fees:
            missing.append("informacji o wpływie prowizji, opłat i obciążeń na wyniki")
        if foreign is not None and not warned:
            missing.append(f"ostrzeżenia o wpływie zmian kursów walut (wyniki w walucie obcej, {self.LIT_E})")
        if foreign is None:
            currency = f"ostrzeżenie walutowe niewymagane – wyniki w PLN ({self.LIT_E})"
        else:
            currency = f"ostrzeżenie walutowe zawarte ({self.LIT_E})"
        if not missing:
            return self.result("pass", claims[0], f"Wyniki historyczne z informacją o wpływie opłat; {currency}.")
        quote = foreign if foreign is not None and not warned else claims[0]
        # Every explanation cites lit. e (spec): unless the missing currency warning already does, add the status.
        note = "" if foreign is not None and not warned else f"; {currency}"
        return self.result("fail", quote, f"Wyniki historyczne bez {' ani '.join(missing)}{note}.")
