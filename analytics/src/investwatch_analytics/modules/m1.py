"""M1 finding: an inventory entry for a third-party ad of a registered firm (change analytics-m1-m3, design 5, 13).

Firm data (`firm`), advertiser data (`advertiser`), ad content (`content_excerpt`) and location (`url`);
the score is how certain it is that this is a third-party ad of that firm.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import uuid
from collections.abc import Callable
from datetime import datetime

from ..config import PIPELINE_VERSION
from ..models import AdvertiserRef, Finding, FirmRef, ModelInfo, RuleResult
from ..rules.engine import Catalogue, Context, run_rules
from .llm_note import llm_model_used, mode_sentence

if TYPE_CHECKING:
    from ..llm.judge import LlmJudge

#: The module's legal frame for the LLM system prompt (analytics-llm-p0 design §2).
M1_CONTEXT = (
    "Module M1: material published by someone other than the investment firm (a finfluencer or another "
    "third party). The question is whether it advertises a registered investment firm or its services."
)
from ..rules.scoring import sigmoid_score
from .excerpt import excerpt

#: Signals named in the title when present, strongest ad evidence first.
TITLE_SIGNALS = ("S1.2", "S1.3", "S1.4")
LLM_ONLY = ("S1.5",)


def firm_ref(ctx: Context) -> FirmRef | None:
    match = ctx.firm_match
    if match is None:
        return None
    return FirmRef(name=match.firm.name, registry_id=match.firm.id, registry_type=match.firm.type,
                   authorized=True, match_confidence=match.confidence)


def advertiser_label(advertiser: AdvertiserRef) -> str:
    return advertiser.handle or advertiser.name or "Nieznany autor"


def build_finding(
    ctx: Context,
    catalogue: Catalogue,
    *,
    advertiser: AdvertiserRef,
    now: datetime,
    new_id: Callable[[], str] = lambda: str(uuid.uuid4()),
    judge: "LlmJudge | None" = None,
) -> Finding:
    rules = run_rules(catalogue, ctx, judge, module="M1", module_context=M1_CONTEXT)
    llm_model = llm_model_used(rules, judge)
    firm = firm_ref(ctx)
    title, summary = _texts(rules, firm, advertiser, " (dane demonstracyjne)" if ctx.registry.demo else "",
                            llm_model=llm_model)
    return Finding(
        id=new_id(),
        document_id=ctx.doc.id,
        module="M1",
        score=sigmoid_score(rules, catalogue),
        status="new",
        title=title,
        summary=summary,
        firm=firm,
        advertiser=advertiser,
        rules=rules,
        content_excerpt=excerpt(ctx.doc.text, ctx.pre, rules),
        url=ctx.doc.url,
        platform=ctx.doc.platform,
        detected_at=now,
        updated_at=now,
        model=ModelInfo(pipeline_version=PIPELINE_VERSION, llm=llm_model, embedder=None),
    )


def _texts(rules: list[RuleResult], firm: FirmRef | None, advertiser: AdvertiserRef, demo: str = "", *,
           llm_model: str | None = None) -> tuple[str, str]:
    by_id = {r.rule_id: r for r in rules}
    who = advertiser_label(advertiser)
    firm_name = firm.name if firm else "firmę z rejestru"
    present = [by_id[i].name.lower() for i in TITLE_SIGNALS if i in by_id and by_id[i].result == "fail"]
    # "reklamuje" only when an ad signal fired; a plain mention is not an ad claim (#35 review).
    verb = "reklamuje" if present else "wspomina"
    title = f"{who} {verb} {firm_name}" + (f" ({', '.join(present)})" if present else "")
    label = by_id.get("S1.3")
    if label is not None and label.result == "fail":
        label_text = f"Oznaczenie współpracy: {label.evidence}." if label.evidence else "Oznaczenie współpracy obecne."
    else:
        label_text = "Brak oznaczenia współpracy (nie wyklucza reklamy)."
    unchecked = [by_id[i] for i in LLM_ONLY if i in by_id and by_id[i].evidence is None and by_id[i].result == "uncertain"]
    found = [r for r in rules if r.result == "fail"]
    unsure = [r for r in rules if r.result == "uncertain" and r not in unchecked]
    parts = [f"Materiał podmiotu trzeciego {who} dotyczy firmy z załadowanego rejestru firm{demo}: {firm_name}.", label_text]
    if found:
        parts.append("Wykryte sygnały: " + "; ".join(f"{r.rule_id} {r.name}" for r in found) + ".")
    if unsure:
        parts.append("Do weryfikacji: " + "; ".join(f"{r.rule_id} {r.name}" for r in unsure) + ".")
    if unchecked:
        parts.append("Nie sprawdzono: " + "; ".join(f"{r.rule_id} {r.name}" for r in unchecked)
                     + " (wymaga modelu językowego).")
    parts.append(mode_sentence(rules, llm_model))
    return title, " ".join(parts)
