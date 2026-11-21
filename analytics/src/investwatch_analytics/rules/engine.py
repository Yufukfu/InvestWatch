"""Rule engine: catalogue from YAML, rule base class, evidence safety net.

A rule is a `Rule` subclass registered with `@register`; its metadata (name, severity, legal
basis, dictionaries) lives in `m2_rules.yaml`. Only catalogue entries with `implemented: true` run.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

import yaml

from ..models import RULE_ID_PATTERN, EvidenceLocator, Result, RuleResult, ScrapedDocument
from ..preprocessing import Preprocessed
from ..registry import FirmMatch, Registry

if TYPE_CHECKING:
    from ..llm.judge import LlmJudge

DEFAULT_CATALOGUE = Path(__file__).with_name("m2_rules.yaml")
SEVERITIES = {"high", "medium", "low"}
# `llm:` block on a catalogue entry (analytics-llm-p0, design §1-2): when the engine may defer to the LLM.
LLM_WHEN = {"always", "uncertain"}
# Every rule parameter a rule class reads (rules/m2.py); anything else in the YAML is a typo.
KNOWN_PARAMS = {
    "labels", "prominent_sentences", "negation_before",
    "window", "claim_patterns", "claim_exclude_patterns", "risk_patterns",
    "risk_override_patterns", "risk_exclude_patterns", "footnote_markers",
    # analytics-llm-p0 (M2 P0 rules)
    "figure_patterns", "figure_exclude_patterns", "past_patterns", "future_patterns", "disclaimer_patterns",
    "hiding_regions", "figure_extra_exclude_patterns", "min_ratio",
    "supervisor_patterns", "approval_patterns", "safety_patterns",
    "supervisor_exclude_patterns", "approval_exclude_patterns", "safety_exclude_patterns",
    "amount_patterns", "amount_return_patterns",
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
    llm: dict[str, str] | None = None  # {question, when}; None = never sent to the LLM


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

    def ask_llm(self, ctx: Context, result: RuleResult) -> bool:
        """Whether to defer this rules-only result to the LLM (only entries with an `llm:` block are asked).

        `when: always` defers whenever the rule applies, `when: uncertain` (default) only an `uncertain` result.
        A rule overrides this when its borderline is narrower (R3, R17).
        """
        llm = self.spec.llm
        if llm is None or result.result == "not_applicable":
            return False
        return llm["when"] == "always" or result.result == "uncertain"

    def evaluate(self, ctx: Context) -> RuleResult:  # pragma: no cover - abstract
        raise NotImplementedError

    def result(
        self, result: Result, evidence: str | None, explanation: str,
        locator: EvidenceLocator | None = None,
    ) -> RuleResult:
        return RuleResult(
            rule_id=self.spec.id,
            name=self.spec.name,
            result=result,
            severity=self.spec.severity,
            evidence=evidence,
            explanation=explanation,
            legal_basis=self.spec.legal_basis,
            method="rule",
            evidence_locator=locator,
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
        if not isinstance(data, dict):
            raise CatalogueError(f"{path}: the catalogue root must be a mapping with a `rules` list")
        specs: list[RuleSpec] = []
        seen: set[str] = set()
        for entry in data.get("rules") or []:
            if not isinstance(entry, dict):
                raise CatalogueError(f"{path}: entry {entry!r} is not a mapping")
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
            params = _check_params(path, rule_id, entry.get("params") or {})
            llm = _check_llm(path, rule_id, entry.get("llm"))
            seen.add(rule_id)
            specs.append(RuleSpec(rule_id, entry["name"], entry["severity"], entry.get("legal_basis"),
                                  implemented, params, llm))
        return cls(specs)


def _check_llm(path: Path, rule_id: str, block: Any) -> dict[str, str] | None:
    """`llm: {question: <non-empty string>, when: always | uncertain}`; `when` defaults to `uncertain`."""
    if block is None:
        return None
    if not isinstance(block, dict):
        raise CatalogueError(f"{path}: {rule_id} llm must be a mapping with `question` and `when`")
    unknown = sorted(set(block) - {"question", "when"})
    if unknown:
        raise CatalogueError(f"{path}: {rule_id} llm has unknown key(s) {', '.join(map(str, unknown))}")
    question = block.get("question")
    if not isinstance(question, str) or not question.strip():
        raise CatalogueError(f"{path}: {rule_id} llm.question must be a non-empty string")
    when = block.get("when", "uncertain")
    if not isinstance(when, str) or when not in LLM_WHEN:
        raise CatalogueError(f"{path}: {rule_id} llm.when must be one of {sorted(LLM_WHEN)}, got {when!r}")
    return {"question": question.strip(), "when": when}


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
        if key == "min_ratio" and (
            isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 < value <= 1
        ):
            raise CatalogueError(f"{path}: {rule_id} {key} must be a number in (0, 1]")
        if key == "hiding_regions" and (not isinstance(value, list) or not all(isinstance(v, str) and v for v in value)):
            raise CatalogueError(f"{path}: {rule_id} {key} must be a list of non-empty strings")
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


UNVERIFIED = "Nie udało się potwierdzić cytatu w treści dokumentu; wymaga weryfikacji."


def run_rules(
    catalogue: Catalogue,
    ctx: Context,
    judge: "LlmJudge | None" = None,
    *,
    module: str = "M2",
    module_context: str = "",
) -> list[RuleResult]:
    """Rules first; with a judge, the deferred checks of this module go to the LLM in one call (ADR 0309)."""
    out = []
    deferred: list[tuple[int, RuleSpec]] = []
    for spec in catalogue.implemented:
        rule = _RULES[spec.id](spec)
        if not rule.applies(ctx):
            out.append(rule.result("not_applicable", None, "Reguła nie dotyczy tego materiału."))
            continue
        res = rule.evaluate(ctx)
        if res.evidence is not None and res.evidence not in ctx.doc.text:
            # Safety net (analytics/CLAUDE.md): an unverifiable quote never supports a verdict.
            res = res.model_copy(update={"result": "uncertain", "evidence": None, "explanation": UNVERIFIED})
        if judge is not None and rule.ask_llm(ctx, res):
            deferred.append((len(out), spec))
        out.append(res)
    if deferred:
        out = _refine(out, deferred, judge, ctx, module=module, module_context=module_context)
    return out


def _refine(
    out: list[RuleResult],
    deferred: list[tuple[int, RuleSpec]],
    judge: "LlmJudge",
    ctx: Context,
    *,
    module: str,
    module_context: str,
) -> list[RuleResult]:
    from ..llm.judge import SemanticCheck

    checks = [SemanticCheck(spec.id, spec.llm["question"]) for _, spec in deferred]  # type: ignore[index]
    outcome = judge.judge(module=module, module_context=module_context, text=ctx.doc.text,
                          content_hash=ctx.pre.content_hash, sentences=ctx.pre.sentences, checks=checks)
    out = list(out)
    for index, spec in deferred:
        verdict = outcome.verdicts.get(spec.id)
        if verdict is None:
            continue  # no valid verdict: the rules-only result stands
        before = out[index]
        update = {"result": verdict.result, "evidence": verdict.evidence, "explanation": verdict.explanation,
                  "method": "hybrid" if before.evidence is not None else "llm"}
        if verdict.evidence is not None and verdict.evidence not in ctx.doc.text:
            # Defence in depth: the judge already verified the quote; never trust it blindly.
            update.update({"result": "uncertain", "evidence": None, "explanation": UNVERIFIED})
        out[index] = before.model_copy(update=update)
    return out
