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
SEVERITIES = {"high", "medium", "low"}
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


def register(cls: type[Rule]) -> type[Rule]:
    _RULES[cls.rule_id] = cls
    return cls


def compile_patterns(patterns: list[str]) -> list[re.Pattern]:
    return [re.compile(p, re.IGNORECASE) for p in patterns]


class Catalogue:
    def __init__(self, specs: list[RuleSpec]):
        self.specs = tuple(specs)
        self._by_id = {s.id: s for s in specs}

    @property
    def implemented(self) -> list[RuleSpec]:
        return [s for s in self.specs if s.implemented]

    def get(self, rule_id: str) -> RuleSpec:
        return self._by_id[rule_id]

    @classmethod
    def load(cls, path: Path | None = None) -> "Catalogue":
        from . import m2  # noqa: F401  (registers the rule classes)

        path = path or DEFAULT_CATALOGUE
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            raise CatalogueError(f"{path}: cannot load rule catalogue ({exc})") from exc
        specs: list[RuleSpec] = []
        seen: set[str] = set()
        for entry in data.get("rules") or []:
            rule_id = str(entry.get("id", ""))
            if not re.match(RULE_ID_PATTERN, rule_id) or not rule_id.startswith("R"):
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
            seen.add(rule_id)
            specs.append(RuleSpec(rule_id, entry["name"], entry["severity"], entry.get("legal_basis"),
                                  implemented, dict(entry.get("params") or {})))
        return cls(specs)


def run_rules(catalogue: Catalogue, ctx: Context) -> list[RuleResult]:
    out = []
    for spec in catalogue.implemented:
        rule = _RULES[spec.id](spec)
        if not rule.applies(ctx):
            out.append(rule.result("not_applicable", None, "Reguła nie dotyczy tego materiału."))
            continue
        res = rule.evaluate(ctx)
        if res.evidence is not None and res.evidence not in ctx.doc.text:
            # Safety net (analytics/CLAUDE.md): an unverifiable quote never supports a verdict.
            res = res.model_copy(update={
                "result": "uncertain",
                "evidence": None,
                "explanation": "Nie udało się potwierdzić cytatu w treści dokumentu; wymaga weryfikacji.",
            })
        out.append(res)
    return out
