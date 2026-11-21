"""M2 finding assembly: rule results -> Finding with raw score and Polish title/summary."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING

from ..config import PIPELINE_VERSION
from ..models import Finding, FirmRef, ModelInfo, RuleResult
from ..rules.engine import Catalogue, Context, run_rules

if TYPE_CHECKING:
    from ..llm.judge import LlmJudge

#: The module's legal frame for the LLM system prompt (design §2: each module owns its context).
M2_CONTEXT = (
    "Module M2: marketing material published by an investment firm itself, checked against art. 44 of "
    "Delegated Regulation (EU) 2017/565 and the UKNF criteria for risk information."
)

WEIGHTS = {"high": 3, "medium": 2, "low": 1}
FAIL_VALUE = {"fail": 1.0, "uncertain": 0.5, "pass": 0.0}
EXCERPT_MAX = 500


def score(rules: list[RuleResult]) -> float:
    """Σ(weight·fail) / Σ(weight·applicable); uncertain = half a fail; 0 when nothing applies."""
    applicable = [r for r in rules if r.result in FAIL_VALUE]
    total = sum(WEIGHTS[r.severity] for r in applicable)
    if not total:
        return 0.0
    return round(sum(WEIGHTS[r.severity] * FAIL_VALUE[r.result] for r in applicable) / total, 3)


def build_finding(
    ctx: Context,
    catalogue: Catalogue,
    *,
    now: datetime,
    new_id: Callable[[], str] = lambda: str(uuid.uuid4()),
    judge: "LlmJudge | None" = None,
) -> Finding:
    rules = run_rules(catalogue, ctx, judge, module="M2", module_context=M2_CONTEXT)
    llm_rules = [r.rule_id for r in rules if r.method in ("llm", "hybrid")]
    llm_model = judge.model_name if judge is not None and llm_rules else None
    match = ctx.firm_match
    firm = None
    if match is not None:
        firm = FirmRef(
            name=match.firm.name,
            registry_id=match.firm.id,
            registry_type=match.firm.type,
            authorized=True,  # every registry entry is an authorized firm
            match_confidence=match.confidence,
        )
    title, summary = _texts(rules, firm, llm_model)
    excerpt = ctx.pre.normalized[:EXCERPT_MAX] or None
    return Finding(
        id=new_id(),
        document_id=ctx.doc.id,
        module="M2",
        score=score(rules),
        status="new",
        title=title,
        summary=summary,
        firm=firm,
        rules=rules,
        content_excerpt=excerpt,
        url=ctx.doc.url,
        platform=ctx.doc.platform,
        detected_at=now,
        updated_at=now,
        model=ModelInfo(pipeline_version=PIPELINE_VERSION, llm=llm_model, embedder=None),
    )


def _texts(rules: list[RuleResult], firm: FirmRef | None, llm_model: str | None = None) -> tuple[str, str]:
    who = firm.name if firm else "Nieznana firma"
    failed = [r for r in rules if r.result == "fail"]
    unsure = [r for r in rules if r.result == "uncertain"]
    checked = ", ".join(r.rule_id for r in rules if r.result != "not_applicable")
    skipped = [r for r in rules if r.result == "not_applicable"]
    if failed:
        title = f"{who}: naruszenia – " + ", ".join(r.name for r in failed)
    elif unsure:
        title = f"{who}: do weryfikacji – " + ", ".join(r.name for r in unsure)
    else:
        # name the rules: only R1-R3 run today, so a clean card must not read as a full UKNF check
        title = f"{who}: brak naruszeń w regułach {checked}" if checked else f"{who}: żadna reguła nie miała zastosowania"
    llm_rules = [r.rule_id for r in rules if r.method in ("llm", "hybrid")]
    if checked and llm_model and llm_rules:
        parts = [f"Sprawdzono reguły {checked}; reguły {', '.join(llm_rules)} rozstrzygnięto z pomocą modelu "
                 f"językowego ({llm_model})."]
    elif checked:
        parts = [f"Sprawdzono reguły {checked} w trybie regułowym (bez modelu językowego)."]
    else:
        parts = ["Żadna z reguł nie miała zastosowania (tryb regułowy, bez modelu językowego)."]
    if skipped:
        parts.append("Nie dotyczy: " + "; ".join(f"{r.rule_id} {r.name}" for r in skipped) + ".")
    if failed:
        parts.append("Niespełnione: " + "; ".join(f"{r.rule_id} {r.name}" for r in failed) + ".")
    if unsure:
        parts.append("Do weryfikacji: " + "; ".join(f"{r.rule_id} {r.name}" for r in unsure) + ".")
    if not failed and not unsure:
        parts.append("Nie wykryto naruszeń; pozostałe reguły UKNF nie są jeszcze sprawdzane automatycznie.")
    return title, " ".join(parts)
