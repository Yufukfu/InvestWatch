"""Rule engine: catalogue from YAML, rule base class, evidence safety net.

A rule is a `Rule` subclass registered with `@register`; its metadata (name, severity, legal
basis, dictionaries) lives in `m2_rules.yaml`. Only catalogue entries with `implemented: true` run.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

import yaml

from ..models import RULE_ID_PATTERN, Result, RuleResult, ScrapedDocument
from ..preprocessing import Preprocessed
from ..registry import FirmMatch, Registry

DEFAULT_CATALOGUE = Path(__file__).with_name("m2_rules.yaml")
#: Shipped catalogue per module (M1/M3 signals: change analytics-m1-m3).
MODULE_CATALOGUES = {
    "M1": Path(__file__).with_name("m1_signals.yaml"),
    "M2": DEFAULT_CATALOGUE,
    "M3": Path(__file__).with_name("m3_signals.yaml"),
}
#: Rule id prefix each module's catalogue must use.
_ID_PREFIX = {"M1": "S1.", "M2": "R", "M3": "S3."}
SEVERITIES = {"high", "medium", "low"}
# Every rule parameter a rule class reads (rules/m2.py); anything else in the YAML is a typo.
KNOWN_PARAMS = {
    "labels", "prominent_sentences", "negation_before",
    "window", "claim_patterns", "claim_exclude_patterns", "risk_patterns",
    "risk_override_patterns", "risk_exclude_patterns", "footnote_markers",
}
# M1/M3 signal parameters (rules/m1.py, rules/m3.py). `*_patterns` compile like the M2 ones;
# the plain string lists below must hold non-empty strings.
SIGNAL_STRING_LISTS = {"referral_query_keys", "tracking_query_prefixes", "rel_values", "pl_domain_suffixes"}
KNOWN_PARAMS |= SIGNAL_STRING_LISTS | {
    "phrase_patterns", "verb_patterns", "instrument_patterns", "negation_patterns", "crypto_patterns",
    "currency_patterns", "phone_patterns",
}
_RULES: dict[str, type["Rule"]] = {}


class CatalogueError(ValueError):
    pass


@dataclass(frozen=True)
class RuleSpec:
    id: str
    name: str
    severity: str
    legal_basis: str | None
    implemented: bool
    params: dict[str, Any] = field(default_factory=dict)
    weight: float = 0.0  # M1/M3 only: the signal's weight in σ(bias + Σ w·x)


@dataclass(frozen=True)
class Context:
    doc: ScrapedDocument
    pre: Preprocessed
    firm_match: FirmMatch | None
    registry: Registry


class Rule:
    rule_id: ClassVar[str]

    def __init__(self, spec: RuleSpec):
        self.spec = spec

    def applies(self, ctx: Context) -> bool:
        return True

    def evidence_fields(self, ctx: Context) -> list[str]:
        """Document fields an evidence quote may come from; the text only, unless a signal quotes metadata."""
        return [ctx.doc.text]

    def evaluate(self, ctx: Context) -> RuleResult:  # pragma: no cover - abstract
        raise NotImplementedError

    def result(self, result: Result, evidence: str | None, explanation: str) -> RuleResult:
        return RuleResult(
            rule_id=self.spec.id,
            name=self.spec.name,
            result=result,
            severity=self.spec.severity,
            evidence=evidence,
            explanation=explanation,
            legal_basis=self.spec.legal_basis,
            method="rule",
        )


def metadata_fields(doc: ScrapedDocument) -> list[str]:
    """The text plus the metadata an M1/M3 signal may quote: author name and handle, link hrefs, the URL."""
    fields = [doc.text]
    if doc.author is not None:
        fields += [v for v in (doc.author.name, doc.author.handle) if v]
    fields += [link.href for link in doc.links]
    fields.append(doc.url)
    return fields


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def register(cls: type[Rule]) -> type[Rule]:
    _RULES[cls.rule_id] = cls
    return cls


def compile_patterns(patterns: list[str]) -> list[re.Pattern]:
    return [re.compile(p, re.IGNORECASE) for p in patterns]


class Catalogue:
    def __init__(self, specs: list[RuleSpec], *, module: str = "M2", bias: float = 0.0):
        self.specs = tuple(specs)
        self._by_id = {s.id: s for s in specs}
        self.module = module
        self.bias = bias  # M1/M3 only

    @property
    def implemented(self) -> list[RuleSpec]:
        return [s for s in self.specs if s.implemented]

    def get(self, rule_id: str) -> RuleSpec:
        return self._by_id[rule_id]

    @classmethod
    def load_module(cls, module: str) -> "Catalogue":
        """The shipped catalogue of `module` (M1, M2 or M3)."""
        return cls.load(MODULE_CATALOGUES[module], module=module)

    @classmethod
    def load(cls, path: Path | None = None, *, module: str = "M2") -> "Catalogue":
        from . import m1, m2, m3  # noqa: F401  (registers the rule classes)

        path = path or DEFAULT_CATALOGUE
        if module not in _ID_PREFIX:
            raise CatalogueError(f"{path}: unknown module {module!r}")
        signals = module != "M2"
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            raise CatalogueError(f"{path}: cannot load rule catalogue ({exc})") from exc
        if not isinstance(data, dict):
            raise CatalogueError(f"{path}: the catalogue root must be a mapping with a `rules` list")
        bias = data.get("bias")
        if signals and not _number(bias):
            raise CatalogueError(f"{path}: a {module} catalogue needs a numeric root `bias`")
        specs: list[RuleSpec] = []
        seen: set[str] = set()
        for entry in data.get("rules") or []:
            if not isinstance(entry, dict):
                raise CatalogueError(f"{path}: entry {entry!r} is not a mapping")
            rule_id = str(entry.get("id", ""))
            if not re.match(RULE_ID_PATTERN, rule_id) or not rule_id.startswith(_ID_PREFIX[module]):
                raise CatalogueError(f"{path}: invalid rule id {rule_id!r}")
            if rule_id in seen:
                raise CatalogueError(f"{path}: duplicate rule id {rule_id}")
            if entry.get("severity") not in SEVERITIES:
                raise CatalogueError(f"{path}: {rule_id} has unknown severity {entry.get('severity')!r}")
            if not entry.get("name"):
                raise CatalogueError(f"{path}: {rule_id} has no name")
            implemented = bool(entry.get("implemented", False))
            if implemented and rule_id not in _RULES:
                raise CatalogueError(f"{path}: {rule_id} is marked implemented but has no rule class")
            weight = entry.get("weight")
            if signals and not _number(weight):
                raise CatalogueError(f"{path}: {rule_id} needs a numeric `weight`")
            params = _check_params(path, rule_id, entry.get("params") or {})
            seen.add(rule_id)
            specs.append(RuleSpec(rule_id, entry["name"], entry["severity"], entry.get("legal_basis"),
                                  implemented, params, float(weight) if signals else 0.0))
        return cls(specs, module=module, bias=float(bias) if signals else 0.0)


def _check_params(path: Path, rule_id: str, params: Any) -> dict[str, Any]:
    """Fail at load, not on the first document: every parameter a rule reads is checked here.

    Only known keys are accepted (a typo like `windw` must not silently fall back to a default);
    `*_patterns` lists and `negation_before` compile; `labels` and `footnote_markers` are lists of
    non-empty strings; `window` and `prominent_sentences` are non-negative integers.
    """
    if not isinstance(params, dict):
        raise CatalogueError(f"{path}: {rule_id} params must be a mapping")
    unknown = sorted(set(params) - KNOWN_PARAMS)
    if unknown:
        raise CatalogueError(f"{path}: {rule_id} has unknown param(s) {', '.join(map(str, unknown))}")
    for key, value in params.items():
        if key in SIGNAL_STRING_LISTS and (not isinstance(value, list) or not all(isinstance(v, str) and v for v in value)):
            raise CatalogueError(f"{path}: {rule_id} {key} must be a list of non-empty strings")
        if key == "footnote_markers" and (not isinstance(value, list) or not all(isinstance(v, str) and v for v in value)):
            raise CatalogueError(f"{path}: {rule_id} {key} must be a list of non-empty strings")
        if key == "negation_before":
            if not isinstance(value, str):
                raise CatalogueError(f"{path}: {rule_id} {key} must be a regex string")
            try:
                re.compile(value)
            except re.error as exc:
                raise CatalogueError(f"{path}: {rule_id} {key} is an invalid regex ({exc})") from exc
        if key in ("window", "prominent_sentences") and (
            isinstance(value, bool) or not isinstance(value, int) or value < 0
        ):
            raise CatalogueError(f"{path}: {rule_id} {key} must be a non-negative integer")
        if key.endswith("_patterns") or key == "labels":
            # An empty label becomes a regex that matches anywhere, so R2 would always pass.
            if not isinstance(value, list) or not all(isinstance(v, str) and (v or key != "labels") for v in value):
                raise CatalogueError(f"{path}: {rule_id} {key} must be a list of {'non-empty ' if key == 'labels' else ''}strings")
            if key.endswith("_patterns"):
                try:
                    compile_patterns(value)
                except re.error as exc:
                    raise CatalogueError(f"{path}: {rule_id} {key} has an invalid regex ({exc})") from exc
    return dict(params)


def run_rules(catalogue: Catalogue, ctx: Context) -> list[RuleResult]:
    out = []
    for spec in catalogue.implemented:
        rule = _RULES[spec.id](spec)
        if not rule.applies(ctx):
            out.append(rule.result("not_applicable", None, "Reguła nie dotyczy tego materiału."))
            continue
        res = rule.evaluate(ctx)
        if res.evidence is not None and not any(res.evidence in f for f in rule.evidence_fields(ctx)):
            # Safety net (analytics/CLAUDE.md): an unverifiable quote never supports a verdict.
            res = res.model_copy(update={
                "result": "uncertain",
                "evidence": None,
                "explanation": "Nie udało się potwierdzić cytatu w treści dokumentu; wymaga weryfikacji.",
            })
        out.append(res)
    return out
