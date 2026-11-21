"""Run the pipeline on the gold set and build the report (gold-set-evaluation spec, design decisions 3-4, 7-8).

`Build` wraps whatever this build of analytics has: the M2 catalogue always, the M1/M3 signal catalogues and
the LLM `judge` argument only once `analytics-m1-m3` / `analytics-llm-p0` are merged. The runner asks the
build, so the same code works before and after those changes.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import logging
import uuid
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .. import pipeline
from ..config import PIPELINE_VERSION
from ..models import Finding, ScrapedDocument
from ..registry import Registry
from ..rules.engine import Catalogue
from .gold import GoldItem, rule_status
from .known_ids import MODULES, Catalogues
from .metrics import curve, f1_plateau, recommended_threshold, rule_metrics

log = logging.getLogger(__name__)

EVAL_DIR = Path(__file__).resolve().parents[3] / "eval"  # analytics/eval, /app/eval in the image
DEFAULT_GOLD = EVAL_DIR / "gold.jsonl"
DEFAULT_REGISTRY = EVAL_DIR / "registry.csv"
#: The one source of the default thresholds (ADR 0316); api DEFAULTS and events.DEFAULT_THRESHOLDS are copies.
THRESHOLDS_FILE = EVAL_DIR / "thresholds.json"
#: ADR 0305's original defaults, reported next to the recommendation for comparison (ADR 0316).
ADR_0305_DEFAULTS = {"M1": 0.6, "M2": 0.5, "M3": 0.7}
#: Namespace of the deterministic run id (design decision 7); never change it, or every stored run is "new".
RUN_NAMESPACE = uuid.UUID("6f1d3c2a-9b8e-4d7f-a6c5-0e1f2a3b4c5d")


class Build:
    """What this build can analyze. `catalogues` maps module -> {rule id: implemented} or None."""

    catalogues: Catalogues
    has_judge: bool

    def analyze(self, doc: ScrapedDocument, *, registry: Registry, now: datetime, new_id: Callable[[], str],
                judge: Any = None) -> list[Finding]:  # pragma: no cover - interface
        raise NotImplementedError


@dataclass
class PipelineBuild(Build):
    catalogue: Catalogue
    signals: Any
    catalogues: Catalogues
    has_judge: bool

    def analyze(self, doc, *, registry, now, new_id, judge=None):
        kwargs: dict[str, Any] = {"registry": registry, "catalogue": self.catalogue, "now": now, "new_id": new_id}
        if self.signals is not None:
            kwargs["signals"] = self.signals
        if judge is not None:
            kwargs["judge"] = judge
        return pipeline.analyze(doc, **kwargs)


def _ids(catalogue: Catalogue) -> dict[str, bool]:
    return {s.id: s.implemented for s in catalogue.specs}


def load_build() -> PipelineBuild:
    """Catalogues as the CLI loads them; a bad YAML raises CatalogueError here, before any document."""
    catalogue = Catalogue.load()
    loader = getattr(pipeline, "default_signal_catalogues", None)  # analytics-m1-m3
    signals = loader() if loader is not None else None
    catalogues: dict[str, dict[str, bool] | None] = {"M1": None, "M2": _ids(catalogue), "M3": None}
    if signals is not None:
        catalogues["M1"], catalogues["M3"] = _ids(signals.m1), _ids(signals.m3)
    has_judge = "judge" in inspect.signature(pipeline.analyze).parameters  # analytics-llm-p0
    return PipelineBuild(catalogue, signals, catalogues, has_judge)


def _ids_counter() -> Callable[[], str]:
    counter = iter(range(1, 10**9))
    return lambda: str(uuid.UUID(int=next(counter), version=4))


def _run_id(gold_sha256: str, pipeline_version: str, module: str, points: list[dict]) -> str:
    """Per module, so a change in one module (or `--module`) never re-stores another's unchanged curve."""
    digest = hashlib.sha256(json.dumps(points, sort_keys=True).encode()).hexdigest()
    return str(uuid.uuid5(RUN_NAMESPACE, f"{gold_sha256}|{pipeline_version}|{module}|{digest}"))


def evaluate(
    items: Sequence[GoldItem],
    *,
    registry: Registry,
    build: Build,
    now: datetime,
    gold_sha256: str,
    judge: Any = None,
    modules: Iterable[str] | None = None,
    run_id: str | None = None,
    pipeline_version: str = PIPELINE_VERSION,
) -> dict:
    wanted = [m for m in MODULES if modules is None or m in set(modules)]
    new_id = _ids_counter()
    found: dict[str, dict[str, Finding]] = {}  # gold id -> module -> finding
    errors: list[str] = []
    without_llm = 0
    for item in items:
        try:
            findings = build.analyze(item.document, registry=registry, now=now, new_id=new_id, judge=judge)
        except Exception as exc:  # a gold document that crashes the pipeline is a bug to report, not to hide
            errors.append(item.id)
            log.error("analysis failed", extra={"gold_id": item.id, "error_type": type(exc).__name__})
            findings = []
        found[item.id] = {f.module: f for f in findings}
        if judge is None or not findings or any(f.model is None or f.model.llm is None for f in findings):
            without_llm += 1

    llm_run_id = str(uuid.uuid4())  # an LLM run is not reproducible: always stored as a new run
    report_modules: dict[str, dict] = {}
    for module in wanted:
        labeled = [i for i in items if module in i.expect]
        if not labeled:
            continue
        positives = sum(1 for i in labeled if i.expect[module].positive)
        entry: dict[str, Any] = {"labeled_samples": len(labeled), "positives": positives,
                                 "negatives": len(labeled) - positives}
        if not any(module in f for f in found.values()):
            report_modules[module] = {"status": "not_run", **entry, "points": [], "rules": {}}
            log.warning("module not run", extra={"eval_module": module, "labeled_samples": len(labeled)})
            continue
        pairs = [(found[i.id][module].score if module in found[i.id] else 0.0, i.expect[module].positive)
                 for i in labeled]
        points = curve(pairs)
        rec = recommended_threshold(points)
        mid = run_id or (llm_run_id if judge is not None else _run_id(gold_sha256, pipeline_version, module, points))
        report_modules[module] = {"status": "evaluated", "run_id": mid, **entry, "points": points,
                                  "recommended_threshold": rec,
                                  "f1_plateau": f1_plateau(points),
                                  "at_adr_0305_default": next(p for p in points
                                                              if p["threshold"] == ADR_0305_DEFAULTS[module]),
                                  "at_recommended_threshold": next((p for p in points if p["threshold"] == rec), None),
                                  "rules": _rules(module, labeled, found, build.catalogues)}

    llm = None
    if judge is not None:
        llm = getattr(judge, "model", None) or "configured"
    run = {
        "computed_at": now.isoformat().replace("+00:00", "Z"),
        "gold_sha256": gold_sha256,
        "pipeline_version": pipeline_version,
        "llm": llm,
        "documents": len(items),
        "documents_without_llm": without_llm,
        "origins": dict(sorted(Counter(i.origin for i in items).items())),
        "analysis_errors": errors,
    }
    return {"run": run, "modules": report_modules}


def _rules(module: str, labeled: list[GoldItem], found: dict[str, dict[str, Finding]],
           catalogues: Catalogues) -> dict[str, dict]:
    observations: dict[str, list[tuple[str, str | None]]] = {}
    for item in labeled:
        finding = found[item.id].get(module)
        results = {r.rule_id: r.result for r in finding.rules} if finding is not None else {}
        for rule_id, gold in item.expect[module].rules.items():
            observations.setdefault(rule_id, []).append((gold, results.get(rule_id)))
    out: dict[str, dict] = {}
    for rule_id, obs in sorted(observations.items()):
        status = rule_status(module, rule_id, catalogues)
        if status == "implemented":
            out[rule_id] = {"status": status, **rule_metrics(obs)}
        else:
            labels = {"fail": 0, "pass": 0, "not_applicable": 0}
            for gold, _ in obs:
                labels[gold] += 1
            out[rule_id] = {"status": status, "labels": labels}
    return out


def write_thresholds(path: Path, report: dict) -> dict[str, float]:
    """Write each evaluated module's recommended threshold; a module without one keeps its value in the file."""
    try:
        current = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        current = {}
    if not isinstance(current, dict):
        raise ValueError(f"{path}: not a JSON object of module thresholds")
    for module, entry in report["modules"].items():
        if entry["status"] == "evaluated" and entry.get("recommended_threshold") is not None:
            current[module] = entry["recommended_threshold"]
    missing = [m for m in MODULES if m not in current]
    if missing:
        raise ValueError(f"no threshold for {', '.join(missing)}: evaluate those modules or keep a previous file")
    out = {m: current[m] for m in MODULES}
    Path(path).write_text(json.dumps(out) + "\n", encoding="utf-8", newline="\n")
    return out


def report_json(report: dict) -> str:
    return json.dumps(report, sort_keys=True, ensure_ascii=False, indent=2) + "\n"
