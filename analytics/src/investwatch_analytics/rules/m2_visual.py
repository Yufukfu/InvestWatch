"""Visual M2 rules read from rendered `blocks` (change `analytics-m2-visual-rules`): R5, R7, R8, R13.

Each rule judges each rendered viewport, then the worst viewport decides (`fail` > `uncertain` > `pass`, desktop
first on ties), as R4 and R6 do. Missing rendering data is never a pass. The block helpers are R4's and R6's.
"""

from __future__ import annotations

import math
import re

from ..models import Block, EvidenceLocator, RuleResult
from .engine import Context, register
from .m2 import (
    NO_BLOCKS,
    NO_PAST_PERFORMANCE,
    NO_RENDER_METADATA,
    VIEWPORTS,
    _PastPerformance,
    _RiskWarnings,
    blank_exclusions,
    locate,
    locator_for,
    weighted_median,
)

_SEVERITY = {"fail": 3, "uncertain": 2, "pass": 1}
_HEX = re.compile(r"#[0-9a-fA-F]{6}")  # the contract's colour format; anything else is an unknown colour

Verdict = tuple[str, Block, str]  # (result, block, explanation)


def _trunc(x: float, places: int = 2) -> str:
    """For display, truncated (never rounded up) so it cannot contradict the verdict; Polish decimal comma."""
    factor = 10 ** places
    return f"{math.floor(x * factor) / factor:.{places}f}".replace(".", ",")


def _px(x: float) -> str:
    return f"{x:g}".replace(".", ",")


def worst(verdicts: list[Verdict]) -> Verdict:
    """The most severe viewport verdict; the first (desktop-first) one wins ties."""
    return max(verdicts, key=lambda v: _SEVERITY[v[0]])


def best(states: list[Verdict]) -> Verdict:
    """A viewport's verdict from its blocks' states: one passing block is enough, then uncertain, then fail."""
    return min(states, key=lambda v: _SEVERITY[v[0]])


# ---- R5 exposure and contrast ------------------------------------------------------------------


def _luminance(hex_color: str) -> float:
    """WCAG 2.x relative luminance of `#rrggbb`."""
    channels = []
    for i in (1, 3, 5):
        c = int(hex_color[i:i + 2], 16) / 255
        channels.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    r, g, b = channels
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(fg: str, bg: str) -> float:
    """WCAG contrast ratio (1-21) of two `#rrggbb` colours."""
    hi, lo = sorted((_luminance(fg), _luminance(bg)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


@register
class R5RiskContrast(_RiskWarnings):
    """ZASÓB R5: "umiejscowienie informacji o ryzyku pod kątem kontrastu, przesłonięcia przez inne elementy oraz
    czytelności". A risk block fails when it is not visible or its contrast is below `min_contrast` (WCAG AA 4.5:1).
    Occlusion by another element is not reported by the renderer (follow-ups)."""

    rule_id = "R5"

    def _state(self, b: Block, min_contrast: float) -> Verdict:
        if not b.visible:
            return "fail", b, f"Ostrzeżenie o ryzyku jest niewidoczne na stronie ({b.viewport})."
        if not (isinstance(b.color, str) and _HEX.fullmatch(b.color)
                and isinstance(b.background_color, str) and _HEX.fullmatch(b.background_color)):
            return "uncertain", b, f"Brak danych o kolorach ostrzeżenia o ryzyku – kontrast do weryfikacji ({b.viewport})."
        ratio = contrast_ratio(b.color, b.background_color)
        shown = f"{_trunc(ratio)}:1 ({b.color} na {b.background_color}, {b.viewport})"
        if ratio < min_contrast:
            return "fail", b, f"Ostrzeżenie o ryzyku ma zbyt niski kontrast: {shown}; wymagane co najmniej {_trunc(min_contrast, 1)}:1."
        return "pass", b, f"Ostrzeżenie o ryzyku jest widoczne i kontrastowe: {shown}."

    def evaluate(self, ctx: Context) -> RuleResult:
        if not ctx.doc.blocks:
            return self.result("not_applicable", None, NO_BLOCKS)
        min_contrast = float(self.spec.params.get("min_contrast", 4.5))
        verdicts = []
        for vp in VIEWPORTS:
            risk = [b for b in ctx.doc.blocks if b.viewport == vp and self.is_warning(b.text)]
            if risk:
                verdicts.append(best([self._state(b, min_contrast) for b in risk]))
        if not verdicts:
            return self.no_risk_result(ctx)
        result, b, why = worst(verdicts)
        return self.result(result, self.warning_quote(ctx, b), why, locator_for(b))


# ---- R7 one-click availability -----------------------------------------------------------------


@register
class R7OneClick(_RiskWarnings):
    """ZASÓB R7: "czy wyświetlanie informacji o ryzyku wymaga rozwinięcia, kliknięcia linku lub przejścia na inną
    warstwę". Reads only `requires_interaction`; visibility is R5's, placement R6's."""

    rule_id = "R7"

    @staticmethod
    def _state(b: Block) -> Verdict | None:
        if b.requires_interaction is False:
            return "pass", b, "Ostrzeżenie o ryzyku jest dostępne bez dodatkowego kliknięcia."
        if b.requires_interaction is True:
            return "fail", b, (
                "Ostrzeżenie o ryzyku wymaga rozwinięcia, kliknięcia lub przejścia na inną warstwę "
                f"({b.viewport})."
            )
        return None

    def evaluate(self, ctx: Context) -> RuleResult:
        if not ctx.doc.blocks:
            return self.result("not_applicable", None, NO_BLOCKS)
        verdicts = []
        any_risk = False
        for vp in VIEWPORTS:
            risk = [b for b in ctx.doc.blocks if b.viewport == vp and self.is_warning(b.text)]
            any_risk |= bool(risk)
            states = [self._state(b) for b in risk]
            known = [st for st in states if st is not None]
            if not known:
                continue  # no interaction metadata in this viewport
            verdict = best(known)
            if verdict[0] == "fail" and len(known) < len(states):
                b = next(b for b, st in zip(risk, states) if st is None)
                verdict = "uncertain", b, (
                    "Ostrzeżenie o ryzyku wymaga kliknięcia, a dla innego wystąpienia brak danych, czy jest dostępne "
                    f"bez kliknięcia ({b.viewport})."
                )
            verdicts.append(verdict)
        if not any_risk:
            return self.no_risk_result(ctx)
        if not verdicts:
            return self.result("not_applicable", None, NO_RENDER_METADATA)
        result, b, why = worst(verdicts)
        return self.result(result, self.warning_quote(ctx, b), why, locator_for(b))


# ---- R8 responsiveness -------------------------------------------------------------------------


@register
class R8Responsiveness(_RiskWarnings):
    """ZASÓB R8: on desktop, tablet and phone, "czy tekst nie jest ucinany lub skalowany poniżej czytelności".

    Per rendered viewport: the warning must be visible (missing there while another viewport has it fails), and
    one visible risk block must be unclipped and at least `min_font_px`. One rendered viewport cannot show
    responsiveness: a defect still fails, a clean result is uncertain."""

    rule_id = "R8"

    def _state(self, b: Block, min_px: float) -> Verdict:
        where = f"({b.viewport})"
        if b.font_size_px <= 0:
            return "uncertain", b, f"Ostrzeżenie o ryzyku ma nieczytelny rozmiar czcionki (0 px) w danych renderowania {where}."
        if b.font_size_px < min_px:
            return "fail", b, (
                f"Ostrzeżenie o ryzyku przeskalowane poniżej czytelności: {_px(b.font_size_px)} px, wymagane "
                f"co najmniej {_px(min_px)} px {where}."
            )
        if b.overflow_clipped is True:
            return "fail", b, f"Ostrzeżenie o ryzyku jest ucięte (tekst wychodzi poza widoczny obszar) {where}."
        if b.overflow_clipped is None:
            return "uncertain", b, f"Brak danych, czy ostrzeżenie o ryzyku nie jest ucięte {where}."
        return "pass", b, "Ostrzeżenie o ryzyku jest czytelne i nieucięte we wszystkich widokach."

    def evaluate(self, ctx: Context) -> RuleResult:
        if not ctx.doc.blocks:
            return self.result("not_applicable", None, NO_BLOCKS)
        min_px = float(self.spec.params.get("min_font_px", 12))
        rendered = [vp for vp in VIEWPORTS if any(b.viewport == vp for b in ctx.doc.blocks)]
        risk = {vp: [b for b in ctx.doc.blocks if b.viewport == vp and self.is_warning(b.text)] for vp in rendered}
        anywhere = [b for vp in rendered for b in risk[vp]]
        if not anywhere:
            return self.no_risk_result(ctx)
        verdicts: list[tuple[str, Block, str, EvidenceLocator]] = []
        for vp in rendered:
            visible = [b for b in risk[vp] if b.visible]
            if not visible:
                b = (risk[vp] or anywhere)[0]  # quote the warning that is missing here
                verdicts.append(("fail", b, f"Ostrzeżenie o ryzyku nie jest widoczne w widoku {vp}.",
                                 locator_for(b) if b.viewport == vp else EvidenceLocator(viewport=vp)))
                continue
            result, b, why = best([self._state(b, min_px) for b in visible])
            verdicts.append((result, b, why, locator_for(b)))
        result, b, why, locator = max(verdicts, key=lambda v: _SEVERITY[v[0]])
        if result == "pass" and len(rendered) == 1:
            result, why = "uncertain", (
                f"Strona wyrenderowana tylko w jednym widoku ({rendered[0]}) – nie można ocenić responsywności."
            )
        return self.result(result, self.warning_quote(ctx, b), why, locator)


# ---- R13 dominance of past performance ---------------------------------------------------------

NO_PAST_PERFORMANCE_BLOCK = "Wyniki historyczne nie występują w danych renderowania – reguła nie dotyczy."


def _figure_key(figure: str) -> str:
    return "".join(figure.split()).replace(",", ".")


@register
class R13PastPerformanceDominance(_PastPerformance):
    """ZASÓB R13: "czy wyniki historyczne nie stanowią najbardziej wyeksponowanego elementu informacji".

    A block presents past performance when it holds a sentence of the shared detector (R12a, R12b, R14), or
    restates a return figure of one (a `+120%` headline over "łączna stopa zwrotu 120%"). It dominates its
    viewport with the largest font (ties included), or as the first block above the dominant (length-weighted
    median) size."""

    rule_id = "R13"

    def _figures(self, text: str) -> set[str]:
        """Return figures only: fee and tax percentages are blanked out first, as the detector does."""
        text = blank_exclusions(text, self._pp["figure_x"])
        return {_figure_key(m.group(0)) for p in self._pp["figure"] for m in p.finditer(text)}

    def _quote(self, ctx: Context, b: Block, sentences: list) -> str | None:
        inside = next((s.text for s in sentences if locate(b.text, s.text) is not None), None)
        return inside if inside is not None else locate(ctx.doc.text, b.text)

    def _viewport(self, blocks: list[Block], sentences: list, figures: set[str]) -> tuple[str, Block, str] | None:
        visible = [b for b in blocks if b.visible and b.font_size_px > 0]
        past = [b for b in visible
                if any(locate(b.text, s.text) is not None for s in sentences) or self._figures(b.text) & figures]
        if not past:
            return None
        largest = max(b.font_size_px for b in visible)
        dominant = weighted_median([(b.font_size_px, len(b.text)) for b in visible])
        if all(b.bbox is not None and len(b.bbox) == 4 for b in visible):
            first = min(visible, key=lambda b: (b.bbox[1], b.bbox[0]))
        else:
            first = visible[0]
        vp = past[0].viewport
        for b in past:
            if b.font_size_px >= largest:
                return "fail", b, (
                    f"Wyniki historyczne są najbardziej wyeksponowanym elementem: największa czcionka w widoku "
                    f"({_px(b.font_size_px)} px, {vp})."
                )
        if first in past and first.font_size_px > dominant:
            return "fail", first, (
                f"Wyniki historyczne są pierwszym elementem strony, czcionką {_px(first.font_size_px)} px powyżej "
                f"przeważającej {_px(dominant)} px ({vp})."
            )
        b = past[0]
        return "pass", b, (
            f"Wyniki historyczne nie są najbardziej wyeksponowanym elementem: {_px(b.font_size_px)} px przy "
            f"największej czcionce {_px(largest)} px ({vp})."
        )

    def evaluate(self, ctx: Context) -> RuleResult:
        if not ctx.doc.blocks:
            return self.result("not_applicable", None, NO_BLOCKS)
        sentences = self.past_performance(ctx)
        if not sentences:
            return self.result("not_applicable", None, NO_PAST_PERFORMANCE)
        figures = set().union(*(self._figures(s.text) for s in sentences))
        verdicts = []
        for vp in VIEWPORTS:
            v = self._viewport([b for b in ctx.doc.blocks if b.viewport == vp], sentences, figures)
            if v is not None:
                verdicts.append(v)
        if not verdicts:
            return self.result("not_applicable", None, NO_PAST_PERFORMANCE_BLOCK)
        result, b, why = worst(verdicts)
        return self.result(result, self._quote(ctx, b, sentences), why, locator_for(b))
