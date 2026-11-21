"""M3 signals, rules-only versions (`.docs/analytics-plan.md` §6; change analytics-m1-m3, specs/m3-unauthorized-advice-signals).

Art. 76 u.o.i.f.: advice is a recommendation based on the client's situation (S3.3) and concerning financial
instruments of art. 2-3 (S3.4). Rules only find candidates for those two (`uncertain`); the LLM confirms them
later through the analytics-llm-p0 seam. Plain crypto-assets are not art. 2 instruments (S3.8).
"""

from __future__ import annotations

import re
from functools import cached_property

from ..models import RuleResult
from ..modules.advertiser import is_social, page_host
from ..registry import http_host
from .engine import Context, Rule, compile_patterns, register
from .m1 import MetadataRule, SignalRule, first_hit, poland_marker


def not_found_text(registry) -> str:
    """A "not found" never states a fact about the KNF register: it names the registry that was loaded."""
    return "Podmiotu nie znaleziono w załadowanym rejestrze firm" + (" (dane demonstracyjne)" if registry.demo else "")


CRYPTO_NOTE = "kryptoaktywa nie są wymienione w katalogu z art. 2 u.o.i.f. (załącznik do tematu 3)"


class PhraseRule(SignalRule):
    """`fail` (or `uncertain` for a candidate) on the first phrase of `phrase_patterns`, else `pass`."""

    hit_result = "fail"
    hit_why = ""
    miss_why = ""

    def evaluate(self, ctx: Context) -> RuleResult:
        if m := first_hit(ctx.doc.text, compile_patterns(self.spec.params.get("phrase_patterns", []))):
            return self.result(self.hit_result, m.group(0), self.hit_why)
        return self.result("pass", None, self.miss_why)

    def candidates(self, ctx: Context) -> list[str]:
        """Every sentence holding a phrase (the result quotes only the first)."""
        patterns = compile_patterns(self.spec.params.get("phrase_patterns", []))
        return [s.text for s in ctx.pre.sentences if any(p.search(s.text) for p in patterns)]


class WindowRule(SignalRule):
    """Sentences with a buy/sell/hold form (negations removed first) and a noun within ±`window` sentences."""

    @cached_property
    def _p(self) -> dict:
        p = self.spec.params
        return {
            "verb": compile_patterns(p.get("verb_patterns", [])),
            "instrument": compile_patterns(p.get("instrument_patterns", [])),
            "crypto": compile_patterns(p.get("crypto_patterns", [])),
            "negation": compile_patterns(p.get("negation_patterns", [])),
            "window": int(p.get("window", 1)),
        }

    def _verb_sentences(self, ctx: Context) -> list[int]:
        out = []
        for i, s in enumerate(ctx.pre.sentences):
            text = s.text
            for n in self._p["negation"]:
                text = n.sub(" ", text)
            if any(v.search(text) for v in self._p["verb"]):
                out.append(i)
        return out

    def _near(self, ctx: Context, i: int, patterns: list[re.Pattern]) -> bool:
        w = self._p["window"]
        sentences = ctx.pre.sentences
        return any(p.search(sentences[j].text) for j in range(max(0, i - w), min(len(sentences), i + w + 1))
                   for p in patterns)


@register
class S31NotInRegistry(MetadataRule):
    rule_id = "S3.1"

    def evaluate(self, ctx: Context) -> RuleResult:
        why = not_found_text(ctx.registry)
        author = ctx.doc.author
        if author is not None and (author.handle or "").strip():
            return self.result("fail", author.handle.strip(), f"{why} (autor).")
        if author is not None and (author.name or "").strip():
            return self.result("fail", author.name.strip(), f"{why} (autor).")
        host = http_host(ctx.doc.url)
        if host and not is_social(host):
            return self.result("fail", page_host(ctx.doc.url), f"{why} (adres strony).")
        return self.result("fail", None, f"{why}.")


@register
class S32AdvisoryVocabulary(PhraseRule):
    rule_id = "S3.2"
    hit_why = "Oferta używa słownictwa usług doradczych lub zarządzania portfelem."
    miss_why = "Brak słownictwa usług doradczych."


@register
class S33Personalisation(PhraseRule):
    rule_id = "S3.3"
    hit_result = "uncertain"
    hit_why = "Możliwa personalizacja oferty (sytuacja klienta) – do potwierdzenia przez model językowy."
    miss_why = "Brak sformułowań o dopasowaniu oferty do sytuacji klienta (tryb regułowy)."


@register
class S34InstrumentRecommendation(WindowRule):
    rule_id = "S3.4"

    def candidates(self, ctx: Context) -> list[str]:
        """Every recommending sentence with an instrument nearby (the result quotes only the first)."""
        return [ctx.pre.sentences[i].text for i in self._verb_sentences(ctx) if self._near(ctx, i, self._p["instrument"])]

    def evaluate(self, ctx: Context) -> RuleResult:
        found = self.candidates(ctx)
        if found:
            return self.result(
                "uncertain", found[0],
                "Możliwa rekomendacja nabycia, zbycia lub trzymania instrumentów finansowych (art. 76) – "
                "do potwierdzenia przez model językowy.",
            )
        return self.result("pass", None, "Brak rekomendacji konkretnych instrumentów finansowych (tryb regułowy).")


@register
class S35PaidModel(PhraseRule):
    rule_id = "S3.5"
    hit_why = "Oferta jest odpłatna (abonament, subskrypcja, płatna grupa)."
    miss_why = "Brak oznak odpłatnej oferty."


@register
class S36TargetsPoland(MetadataRule):
    rule_id = "S3.6"

    def evaluate(self, ctx: Context) -> RuleResult:
        return poland_marker(self, ctx)


@register
class S38CryptoOutsideArt2(WindowRule):
    rule_id = "S3.8"

    def evaluate(self, ctx: Context) -> RuleResult:
        for i in self._verb_sentences(ctx):
            if self._near(ctx, i, self._p["crypto"]) and not self._near(ctx, i, self._p["instrument"]):
                return self.result(
                    "fail", ctx.pre.sentences[i].text,
                    f"Rekomendacje kupna lub sprzedaży kryptoaktywów, poza art. 2: {CRYPTO_NOTE}.",
                )
        return self.result("pass", None, "Brak rekomendacji dotyczących wyłącznie kryptoaktywów.")
