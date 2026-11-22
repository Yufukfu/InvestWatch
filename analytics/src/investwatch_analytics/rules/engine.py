"""Rule engine: catalogue from YAML, rule base class, evidence safety net.

A rule is a `Rule` subclass registered with `@register`; its metadata (name, severity, legal
basis, dictionaries) lives in `m2_rules.yaml`. Only catalogue entries with `implemented: true` run.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

import yaml

try:  # CPython's own regex parser; renamed from `sre_parse` in 3.11 (tests/test_regex_safety.py pins its shape)
    import re._parser as _sre_parser
except ImportError:  # pragma: no cover - older CPython
    import sre_parse as _sre_parser  # type: ignore[no-redef]

from ..models import RULE_ID_PATTERN, EvidenceLocator, Result, RuleResult, ScrapedDocument
from ..preprocessing import Preprocessed
from ..registry import FirmMatch, Registry

if TYPE_CHECKING:
    from ..llm.judge import LlmJudge, LlmVerdict

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
    "borderline_margin",
    # analytics-m2-p1-rules (R11, R12a, R12b, R15, R16; design §9)
    "comparison_patterns", "comparison_exclude_patterns", "benchmark_patterns", "superlative_patterns",
    "source_patterns", "assumption_patterns",
    "short_period_patterns", "five_year_patterns", "inception_patterns",
    "fee_patterns", "foreign_currency_patterns", "currency_warning_patterns",
    "forecast_patterns", "forecast_verb_patterns", "forecast_exclude_patterns", "forecast_weak_patterns",
    "performance_patterns", "forecast_disclaimer_patterns",
    "tax_patterns", "tax_exclude_patterns", "tax_individual_patterns", "tax_change_patterns", "tax_context_patterns",
    "tax_subject_patterns",
    # analytics-m2-text-rules (R9)
    "jargon_patterns", "max_avg_sentence_words", "max_jargon_share", "min_jargon_hits",
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
    llm: dict[str, str] | None = None  # {question, when}; None = never sent to the LLM
    # M2 only: a rules-only `uncertain` carries no evidence of an infringement and is left out of the score; only
    # an LLM verdict counts (R9, change analytics-m2-text-rules). The finding still lists the result.
    llm_only_uncertain: bool = False


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

    def accept_llm_verdict(self, verdict: "LlmVerdict") -> "LlmVerdict":
        """Narrow an LLM verdict before it replaces the rules-only result; the default keeps it (R9 overrides)."""
        return verdict

    def evidence_fields(self, ctx: Context) -> list[str]:
        """Document fields an evidence quote may come from; the text only, unless a signal quotes metadata."""
        return [ctx.doc.text]

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


def metadata_fields(doc: ScrapedDocument) -> list[str]:
    """The text plus the metadata an M1/M3 signal may quote: author name and handle, link hrefs, the URL."""
    fields = [doc.text]
    if doc.author is not None:
        fields += [v for v in (doc.author.name, doc.author.handle) if v]
    fields += [link.href for link in doc.links]
    fields.append(doc.url)
    return fields


def _number(value: Any) -> bool:
    # NaN and infinities are floats but would make every score NaN or 0/1 without an error.
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def register(cls: type[Rule]) -> type[Rule]:
    _RULES[cls.rule_id] = cls
    return cls


def compile_patterns(patterns: list[str]) -> list[re.Pattern]:
    return [re.compile(p, re.IGNORECASE) for p in patterns]


_REPEATS = {_sre_parser.MAX_REPEAT, _sre_parser.MIN_REPEAT, getattr(_sre_parser, "POSSESSIVE_REPEAT", None)} - {None}


def nested_unbounded_repeat(pattern: str) -> bool:
    r"""True when an unbounded repetition (`*`, `+`, `{n,}`) sits inside another one, e.g. `(\w+\s*)+`.

    Such a pattern can backtrack exponentially on untrusted text and Python `re` has no timeout (design §8).
    Bounded outer repeats (`(?:\w+\s+){0,3}`) are allowed; alternation overlap is left to the timing test.
    """

    def walk(node, inside: bool) -> bool:
        if isinstance(node, _sre_parser.SubPattern):
            return any(walk(item, inside) for item in node.data)
        # Identity, not equality: opcodes are named-int singletons, and a class range `[+-9]` is a plain
        # (43, 57) pair whose first int equals MIN_REPEAT (review of group 1).
        if isinstance(node, tuple) and len(node) == 2 and any(node[0] is r for r in _REPEATS):
            low, high, body = node[1]
            unbounded = high == _sre_parser.MAXREPEAT
            if unbounded and inside:
                return True
            return walk(body, inside or unbounded)
        if isinstance(node, (tuple, list)):
            return any(walk(item, inside) for item in node)
        return False

    return walk(_sre_parser.parse(pattern, re.IGNORECASE), False)


def _check_regex(path: Path, rule_id: str, key: str, pattern: str) -> None:
    if nested_unbounded_repeat(pattern):
        raise CatalogueError(
            f"{path}: {rule_id} {key} has a nested unbounded repetition (ReDoS risk): {pattern!r}; "
            r"use a bounded gap such as (?:\w+\s+){0,3} or .{0,80}?"
        )


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
        from . import m1, m2, m2_text, m3  # noqa: F401  (registers the rule classes)

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
            llm = _check_llm(path, rule_id, entry.get("llm"))
            llm_only_uncertain = entry.get("llm_only_uncertain", False)
            if not isinstance(llm_only_uncertain, bool):
                raise CatalogueError(f"{path}: {rule_id} llm_only_uncertain must be true or false")
            seen.add(rule_id)
            specs.append(RuleSpec(rule_id, entry["name"], entry["severity"], entry.get("legal_basis"),
                                  implemented, params, weight=float(weight) if signals else 0.0, llm=llm,
                                  llm_only_uncertain=llm_only_uncertain))
        return cls(specs, module=module, bias=float(bias) if signals else 0.0)


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
            _check_regex(path, rule_id, key, value)
        if key in ("window", "prominent_sentences", "borderline_margin") and (
            isinstance(value, bool) or not isinstance(value, int) or value < 0
        ):
            raise CatalogueError(f"{path}: {rule_id} {key} must be a non-negative integer")
        if key == "min_ratio" and (
            isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 < value <= 1
        ):
            raise CatalogueError(f"{path}: {rule_id} {key} must be a number in (0, 1]")
        if key in ("max_avg_sentence_words", "min_jargon_hits") and (
            isinstance(value, bool) or not isinstance(value, int) or value < 1
        ):
            raise CatalogueError(f"{path}: {rule_id} {key} must be a positive integer")
        if key == "max_jargon_share" and (
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
                for pattern in value:
                    _check_regex(path, rule_id, key, pattern)
    return dict(params)


UNVERIFIED = "Nie udało się potwierdzić cytatu w treści dokumentu; wymaga weryfikacji."


def run_rules(
    catalogue: Catalogue,
    ctx: Context,
    judge: "LlmJudge | None" = None,
    *,
    module: str | None = None,
    module_context: str = "",
) -> list[RuleResult]:
    """Rules first; with a judge, the deferred checks of this module go to the LLM in one call (ADR 0309).

    `module` defaults to the catalogue's own module, so M3 checks are never sent labelled M2.
    """
    module = module or catalogue.module
    out = []
    deferred: list[tuple[int, RuleSpec]] = []
    for spec in catalogue.implemented:
        rule = _RULES[spec.id](spec)
        if not rule.applies(ctx):
            out.append(rule.result("not_applicable", None, "Reguła nie dotyczy tego materiału."))
            continue
        res = rule.evaluate(ctx)
        if res.evidence is not None and not any(res.evidence in f for f in rule.evidence_fields(ctx)):
            # Safety net (analytics/CLAUDE.md): an unverifiable quote never supports a verdict.
            res = res.model_copy(update={"result": "uncertain", "evidence": None, "explanation": UNVERIFIED})
        if judge is not None and spec.llm is not None and rule.ask_llm(ctx, res):
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

    checks = [SemanticCheck(spec.id, spec.llm["question"]) for _, spec in deferred if spec.llm is not None]
    outcome = judge.judge(module=module, module_context=module_context, text=ctx.doc.text,
                          content_hash=ctx.doc.content_hash, sentences=ctx.pre.sentences, checks=checks)
    out = list(out)
    for index, spec in deferred:
        verdict = outcome.verdicts.get(spec.id)
        if verdict is None:
            continue  # no valid verdict: the rules-only result stands
        verdict = _RULES[spec.id](spec).accept_llm_verdict(verdict)
        before = out[index]
        update = {"result": verdict.result, "evidence": verdict.evidence, "explanation": verdict.explanation,
                  "method": "hybrid" if before.evidence is not None else "llm"}
        if verdict.evidence != before.evidence:
            update["evidence_locator"] = None  # the locator pointed at the rules-only quote
        if verdict.evidence is not None and verdict.evidence not in ctx.doc.text:
            # Defence in depth: the judge already verified the quote; never trust it blindly.
            update.update({"result": "uncertain", "evidence": None, "explanation": UNVERIFIED})
        out[index] = before.model_copy(update=update)
    return out
