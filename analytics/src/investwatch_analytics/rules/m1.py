"""M1 signals, rules-only versions (`.docs/analytics-plan.md` §4; change analytics-m1-m3, specs/m1-third-party-signals).

`fail` means the signal is present. Signals that quote metadata (author, links, URL) declare it through
`evidence_fields`, so the engine's safety net checks the quote against those fields too.
"""

from __future__ import annotations

import re
from functools import cached_property

from ..models import RuleResult
from ..modules.advertiser import firm_named_by_handle, is_social, page_host, publisher_firm
from ..registry import http_host
from .engine import Context, Rule, compile_patterns, metadata_fields, register


#: Longest evidence quote on an M1/M3 signal; a prefix of a verbatim quote is still verbatim.
EVIDENCE_MAX = 300


class SignalRule(Rule):
    """An M1/M3 signal: its evidence is cut to EVIDENCE_MAX, so a 2 MB sentence never lands in a finding."""

    def result(self, result, evidence, explanation):
        return super().result(result, evidence[:EVIDENCE_MAX] if evidence else evidence, explanation)


class MetadataRule(SignalRule):
    """A signal whose evidence may quote the author, a link href or the page URL."""

    def evidence_fields(self, ctx: Context) -> list[str]:
        return metadata_fields(ctx.doc)


def word_patterns(words: list[str]) -> list[re.Pattern]:
    """Literal labels as case-insensitive whole-word regexes (whitespace inside a label matches any run)."""
    return [
        re.compile(r"(?<!\w)" + r"\s+".join(map(re.escape, w.split())) + r"(?!\w)", re.IGNORECASE) for w in words
    ]


def first_hit(text: str, patterns: list[re.Pattern]) -> re.Match | None:
    hits = [m for p in patterns if (m := p.search(text))]
    return min(hits, key=lambda m: m.start()) if hits else None


def poland_marker(rule: Rule, ctx: Context) -> RuleResult:
    """S1.7 / S3.6: PLN or złoty amount, +48 number, a .pl page host, else the Polish language guess."""
    p = rule.spec.params
    text = ctx.doc.text
    for key, why in (("currency_patterns", "Kwota w złotych"), ("phone_patterns", "Polski numer telefonu")):
        if m := first_hit(text, compile_patterns(p.get(key, []))):
            return rule.result("fail", m.group(0).strip(), f"{why} wskazuje na odbiorców w Polsce.")
    host = page_host(ctx.doc.url)
    if any(host.lower().endswith(s) for s in p.get("pl_domain_suffixes", [])):
        return rule.result("fail", host, "Domena .pl w adresie strony wskazuje na odbiorców w Polsce.")
    if ctx.pre.lang == "pl":
        return rule.result("fail", None, "Materiał jest w języku polskim.")
    return rule.result("pass", None, "Brak oznak kierowania treści do odbiorców w Polsce.")


@register
class S11FirmMention(MetadataRule):
    rule_id = "S1.1"

    def evaluate(self, ctx: Context) -> RuleResult:
        match = ctx.firm_match
        if match is None:
            return self.result("pass", None, "Materiał nie wymienia firmy z załadowanego rejestru firm.")
        name = match.firm.name
        if match.method == "name":
            return self.result("fail", match.evidence, f"Materiał wymienia firmę z załadowanego rejestru firm: {name}.")
        if match.method == "link":
            return self.result("fail", match.evidence, f"Materiał zawiera link do domeny firmy z załadowanego rejestru firm: {name}.")
        if match.method == "domain":
            return self.result("fail", page_host(ctx.doc.url), f"Adres strony należy do firmy z załadowanego rejestru firm: {name}.")
        return self.result("uncertain", None, f"Możliwa wzmianka o firmie {name} (dopasowanie przybliżone) – do weryfikacji.")


@register
class S12Referral(MetadataRule):
    rule_id = "S1.2"

    @cached_property
    def _query(self) -> tuple[re.Pattern | None, re.Pattern | None]:
        def key_re(keys: list[str], prefix: bool) -> re.Pattern | None:
            if not keys:
                return None
            alt = "|".join(re.escape(k) for k in keys)
            name = rf"(?:{alt})[^=&#]*" if prefix else rf"(?:{alt})"
            return re.compile(rf"(?<=[?&]){name}=[^&#]*", re.IGNORECASE)

        p = self.spec.params
        return key_re(p.get("referral_query_keys", []), False), key_re(p.get("tracking_query_prefixes", []), True)

    @staticmethod
    def _query_part(href: str, pattern: re.Pattern | None) -> str | None:
        if pattern is None or http_host(href) is None:
            return None
        q = href.find("?")
        m = pattern.search(href, q) if q >= 0 else None
        return m.group(0) if m else None

    def evaluate(self, ctx: Context) -> RuleResult:
        referral, tracking = self._query
        for link in ctx.doc.links:
            if quote := self._query_part(link.href, referral):
                return self.result("fail", quote, "Link z parametrem polecającym (afiliacyjnym) w linku materiału.")
        if m := first_hit(ctx.doc.text, compile_patterns(self.spec.params.get("phrase_patterns", []))):
            return self.result("fail", m.group(0), "Kod lub link polecający w treści materiału.")
        for link in ctx.doc.links:
            if quote := self._query_part(link.href, tracking):
                return self.result(
                    "uncertain", quote, "Link ze znacznikami śledzenia (utm) w linku materiału – możliwa afiliacja.",
                )
        return self.result("pass", None, "Brak linku afiliacyjnego i kodu polecającego.")


@register
class S13PartnershipLabel(MetadataRule):
    rule_id = "S1.3"

    @cached_property
    def _labels(self) -> list[re.Pattern]:
        return word_patterns(self.spec.params.get("labels", []))

    @cached_property
    def _negation(self) -> re.Pattern | None:
        pattern = self.spec.params.get("negation_before")
        return re.compile(pattern, re.IGNORECASE) if pattern else None

    def _negated(self, text: str, m: re.Match) -> bool:
        if m.group(0).startswith("#") or self._negation is None:
            return False
        return bool(self._negation.search(text, max(0, m.start() - 40), m.start()))

    def evaluate(self, ctx: Context) -> RuleResult:
        text = ctx.doc.text
        hits = sorted((m for p in self._labels for m in p.finditer(text) if not self._negated(text, m)),
                      key=lambda m: m.start())
        if hits:
            return self.result("fail", hits[0].group(0), "Materiał jest oznaczony jako współpraca lub reklama.")
        rels = {r.lower() for r in self.spec.params.get("rel_values", [])}
        for link in ctx.doc.links:
            if rels & set((link.rel or "").lower().split()):
                return self.result("fail", link.href, "Link oznaczony jako sponsorowany (rel=sponsored) w linku materiału.")
        return self.result("pass", None, "Brak oznaczenia współpracy (to nie wyklucza reklamy).")


@register
class S14CallToAction(SignalRule):
    rule_id = "S1.4"

    def ask_llm(self, ctx: Context, result: RuleResult) -> bool:
        """analytics-llm-p0 seam: the LLM may add an implicit call to action, never remove a dictionary hit."""
        return result.result == "pass"

    def evaluate(self, ctx: Context) -> RuleResult:
        if m := first_hit(ctx.doc.text, compile_patterns(self.spec.params.get("phrase_patterns", []))):
            return self.result("fail", m.group(0), "Materiał wzywa do działania (konto, rejestracja, link, kod).")
        return self.result("pass", None, "Brak wezwania do działania w słowniku reguł.")


@register
class S15Promotional(SignalRule):
    rule_id = "S1.5"

    def evaluate(self, ctx: Context) -> RuleResult:
        return self.result(
            "uncertain", None,
            "Ocena, czy treść jest promocyjna, wymaga modelu językowego – nie sprawdzono w trybie regułowym.",
        )


@register
class S16AuthorNotFirm(MetadataRule):
    rule_id = "S1.6"

    def evaluate(self, ctx: Context) -> RuleResult:
        match = ctx.firm_match
        publisher = publisher_firm(ctx.doc, ctx.registry)
        if match is not None and publisher is not None and publisher.id == match.firm.id:
            return self.result("pass", None, "Autorem jest sama firma.")
        author = ctx.doc.author
        named = firm_named_by_handle(ctx.doc, ctx.registry)
        if match is not None and named is not None and named.id == match.firm.id:
            return self.result("uncertain", author.handle.strip(),
                               "Nazwa konta jak nazwa firmy, ale nie potwierdzono, że konto należy do firmy (autor).")
        if author is not None and (author.handle or "").strip():
            return self.result("fail", author.handle.strip(), "Autor materiału nie jest firmą inwestycyjną.")
        if author is not None and (author.name or "").strip():
            return self.result("fail", author.name.strip(), "Autor materiału nie jest firmą inwestycyjną.")
        host = http_host(ctx.doc.url)
        if host and not is_social(host):
            return self.result("fail", page_host(ctx.doc.url), "Adres strony nie należy do firmy inwestycyjnej.")
        return self.result("not_applicable", None, "Brak danych o autorze materiału.")


@register
class S17TargetsPoland(MetadataRule):
    rule_id = "S1.7"

    def evaluate(self, ctx: Context) -> RuleResult:
        return poland_marker(self, ctx)
