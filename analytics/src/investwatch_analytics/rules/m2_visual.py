"""Visual M2 rules read from rendered `blocks` (change `analytics-m2-visual-rules`): R5, R7, R8, R13.

Each rule judges each rendered viewport, then the worst viewport decides (`fail` > `uncertain` > `pass`, desktop
first on ties), as R4 and R6 do. Missing rendering data is never a pass. The block helpers are R4's and R6's.
"""

from __future__ import annotations

import math
import re

from ..models import Block, RuleResult
from .engine import Context, register
from .m2 import NO_BLOCKS, NO_RENDER_METADATA, VIEWPORTS, _RiskWarnings, locator_for

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
