"""M2 finding assembly: rule results -> Finding with raw score and Polish title/summary."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime

from ..config import PIPELINE_VERSION
from ..models import Finding, FirmRef, ModelInfo, RuleResult
from ..rules.engine import Catalogue, Context, run_rules

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
) -> Finding:
    rules = run_rules(catalogue, ctx)
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
    title, summary = _texts(rules, firm)
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
        model=ModelInfo(pipeline_version=PIPELINE_VERSION, llm=None, embedder=None),
    )


def _texts(rules: list[RuleResult], firm: FirmRef | None) -> tuple[str, str]:
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
    if checked:
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
