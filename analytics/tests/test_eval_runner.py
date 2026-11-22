"""gold-set-evaluation: module scores, "Module that never ran", per-rule wiring, determinism and the run id."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from conftest import make_doc
from investwatch_analytics.evaluation.gold import GoldItem, ModuleExpectation
from investwatch_analytics.evaluation.runner import (
    DEFAULT_REGISTRY,
    Build,
    evaluate,
    load_build,
    report_json,
)
from investwatch_analytics.models import Finding, ModelInfo, RuleResult, ScrapedDocument
from investwatch_analytics.registry import Registry

NOW = datetime(2026, 11, 21, 23, 0, tzinfo=timezone.utc)
GOLD_SHA = "a" * 64


def item(n: int, expect: dict, *, origin: str = "synthetic", **doc) -> GoldItem:
    document = ScrapedDocument.model_validate(make_doc(id=f"00000000-0000-4000-8000-{n:012d}", **doc))
    return GoldItem(n, f"g{n}", origin, "test", None, document,
                    {m: ModuleExpectation(label, rules) for m, (label, rules) in expect.items()})


def finding(doc: ScrapedDocument, module: str, score: float, rules: dict[str, str] | None = None,
            llm: str | None = None) -> Finding:
    return Finding(
        id="00000000-0000-4000-8000-ffffffffffff", document_id=doc.id, module=module, score=score,
        title="t", url=doc.url, platform=doc.platform, detected_at=NOW, updated_at=NOW,
        rules=[RuleResult(rule_id=r, name=r, result=v, severity="high") for r, v in (rules or {}).items()],
        model=ModelInfo(pipeline_version="0.1.0", llm=llm),
    )


class FakeBuild(Build):
    """Canned findings per document id; catalogues as a build with M1 and M2."""

    def __init__(self, out: dict[str, list[tuple]], catalogues=None, has_judge=False):
        self.out = out
        self.catalogues = catalogues or {"M1": {"S1.2": True}, "M2": {"R3": True, "R5": False}, "M3": None}
        self.has_judge = has_judge

    def analyze(self, doc, *, registry, now, new_id, judge=None):
        if judge is not None:
            judge()  # FakeJudge below raises: the build must degrade to rules-only like the pipeline does
        return [finding(doc, *spec) for spec in self.out.get(doc.id, [])]


def run(items, build, **kw):
    registry = Registry.from_csv(DEFAULT_REGISTRY)
    return evaluate(items, registry=registry, build=build, now=NOW, gold_sha256=GOLD_SHA, **kw)


def at(report, module, threshold):
    return next(p for p in report["modules"][module]["points"] if p["threshold"] == threshold)


def test_module_score_is_the_finding_score():
    a, b = item(1, {"M2": ("positive", {})}), item(2, {"M2": ("negative", {})})
    build = FakeBuild({a.document.id: [("M2", 0.8)], b.document.id: [("M2", 0.3)]})
    report = run([a, b], build)
    m2 = report["modules"]["M2"]
    assert m2["status"] == "evaluated" and m2["labeled_samples"] == 2
    assert (m2["positives"], m2["negatives"]) == (1, 1)
    assert {k: at(report, "M2", 0.5)[k] for k in ("tp", "fp", "fn", "tn")} == {"tp": 1, "fp": 0, "fn": 0, "tn": 1}
    assert {k: at(report, "M2", 0.85)[k] for k in ("tp", "fn")} == {"tp": 0, "fn": 1}


def test_no_finding_is_a_zero_score():
    a = item(1, {"M1": ("positive", {})})
    b = item(2, {"M1": ("negative", {})})
    build = FakeBuild({a.document.id: [("M2", 0.9)], b.document.id: [("M1", 0.9)]})
    report = run([a, b], build)
    assert all(p["fn"] == 1 and p["tp"] == 0 for p in report["modules"]["M1"]["points"])


def test_module_that_never_ran():
    a = item(1, {"M1": ("positive", {"S1.2": "fail"}), "M2": ("positive", {})})
    build = FakeBuild({a.document.id: [("M2", 0.9)]})
    report = run([a], build)
    assert report["modules"]["M1"] == {"status": "not_run", "labeled_samples": 1, "positives": 1, "negatives": 0,
                                       "points": [], "rules": {}}
    assert report["modules"]["M2"]["status"] == "evaluated"


def test_module_without_labels_is_not_reported():
    a = item(1, {"M2": ("positive", {})})
    report = run([a], FakeBuild({a.document.id: [("M2", 0.9), ("M3", 0.9)]}))
    assert set(report["modules"]) == {"M2"}


def test_module_filter():
    a = item(1, {"M1": ("positive", {}), "M2": ("positive", {})})
    report = run([a], FakeBuild({a.document.id: [("M1", 0.9), ("M2", 0.9)]}), modules=["M2"])
    assert set(report["modules"]) == {"M2"}


def test_rule_metrics_and_statuses():
    a = item(1, {"M2": ("positive", {"R3": "fail", "R5": "fail", "R14": "pass"})})
    b = item(2, {"M2": ("negative", {"R3": "pass"})})
    build = FakeBuild({a.document.id: [("M2", 0.9, {"R3": "uncertain"})], b.document.id: [("M2", 0.1, {"R3": "pass"})]})
    rules = run([a, b], build)["modules"]["M2"]["rules"]
    assert rules["R3"]["status"] == "implemented"
    assert (rules["R3"]["strict"]["fn"], rules["R3"]["review"]["tp"], rules["R3"]["uncertain"]) == (1, 1, 1)
    assert rules["R5"] == {"status": "not_implemented", "labels": {"fail": 1, "pass": 0, "not_applicable": 0}}
    assert rules["R14"] == {"status": "not_in_build", "labels": {"fail": 0, "pass": 1, "not_applicable": 0}}


def test_two_runs_are_identical_except_run_and_time():
    items = [item(1, {"M2": ("positive", {"R3": "fail"})}), item(2, {"M2": ("negative", {})})]
    build = load_build()
    first = json.loads(report_json(run(items, build)))
    second = json.loads(report_json(run(items, build)))
    assert first == second  # same now and gold hash: even the run id is equal
    later = json.loads(report_json(evaluate(items, registry=Registry.from_csv(DEFAULT_REGISTRY), build=build,
                                            now=datetime(2026, 11, 22, tzinfo=timezone.utc), gold_sha256=GOLD_SHA)))
    for r in (first, later):
        del r["run"]["computed_at"]
    assert first == later


def test_report_json_is_sorted_and_stable():
    a = item(1, {"M2": ("positive", {})})
    text = report_json(run([a], FakeBuild({a.document.id: [("M2", 0.9)]})))
    assert text == json.dumps(json.loads(text), sort_keys=True, ensure_ascii=False, indent=2) + "\n"


def run_id(items, build, gold=GOLD_SHA, version=None):
    kw = {"pipeline_version": version} if version else {}
    return evaluate(items, registry=Registry.from_csv(DEFAULT_REGISTRY), build=build, now=NOW, gold_sha256=gold,
                    **kw)["modules"]["M2"]["run_id"]


def test_deterministic_run_id_inputs():
    a = item(1, {"M2": ("positive", {})})
    build = FakeBuild({a.document.id: [("M2", 0.9)]})
    base = run_id([a], build)
    assert base == run_id([a], build)
    assert base != run_id([a], build, gold="b" * 64)
    assert base != run_id([a], build, version="9.9.9")
    assert base != run_id([a], FakeBuild({a.document.id: [("M2", 0.4)]}))  # a point changed
    assert len(base) == 36 and base[14] == "5"  # UUID v5


def test_explicit_run_id_wins():
    a = item(1, {"M2": ("positive", {})})
    rid = "12345678-1234-4234-8234-123456789012"
    assert run([a], FakeBuild({a.document.id: [("M2", 0.9)]}), run_id=rid)["modules"]["M2"]["run_id"] == rid


def test_run_id_is_per_module():
    a = item(1, {"M1": ("positive", {}), "M2": ("positive", {})})
    full = run([a], FakeBuild({a.document.id: [("M1", 0.9), ("M2", 0.9)]}))
    m1_changed = run([a], FakeBuild({a.document.id: [("M1", 0.2), ("M2", 0.9)]}))
    only_m2 = run([a], FakeBuild({a.document.id: [("M1", 0.9), ("M2", 0.9)]}), modules=["M2"])
    assert full["modules"]["M2"]["run_id"] == m1_changed["modules"]["M2"]["run_id"] == only_m2["modules"]["M2"]["run_id"]
    assert full["modules"]["M1"]["run_id"] != m1_changed["modules"]["M1"]["run_id"]
    assert full["modules"]["M1"]["run_id"] != full["modules"]["M2"]["run_id"]


def test_llm_run_gets_random_ids():
    a = item(1, {"M2": ("positive", {})})
    build = FakeBuild({a.document.id: [("M2", 0.9)]})
    first = run([a], build, judge=lambda: None)["modules"]["M2"]["run_id"]
    assert first != run([a], build, judge=lambda: None)["modules"]["M2"]["run_id"]
    assert first[14] == "4"


def test_not_run_module_has_no_run_id():
    a = item(1, {"M1": ("positive", {}), "M2": ("positive", {})})
    assert "run_id" not in run([a], FakeBuild({a.document.id: [("M2", 0.9)]}))["modules"]["M1"]


def test_origins_are_counted():
    items = [item(1, {"M2": ("positive", {})}), item(2, {"M2": ("negative", {})}, origin="uknf-sample")]
    report = run(items, FakeBuild({}))
    assert report["run"]["origins"] == {"synthetic": 1, "uknf-sample": 1}
    assert report["run"]["documents"] == 2


def test_documents_without_llm():
    a, b = item(1, {"M2": ("positive", {})}), item(2, {"M2": ("negative", {})})
    build = FakeBuild({a.document.id: [("M2", 0.9, None, "gemma3:4b")], b.document.id: [("M2", 0.1)]})
    report = run([a, b], build, judge=lambda: None)
    assert report["run"]["documents_without_llm"] == 1
    assert run([a, b], build)["run"]["documents_without_llm"] == 2  # rules-only: none used the model


def test_analysis_error_counts_and_skips_the_document():
    a, b = item(1, {"M2": ("positive", {})}), item(2, {"M2": ("negative", {})})

    class Exploding(FakeBuild):
        def analyze(self, doc, **kw):
            if doc.id == a.document.id:
                raise RuntimeError("boom")
            return super().analyze(doc, **kw)

    report = run([a, b], Exploding({b.document.id: [("M2", 0.1)]}))
    assert report["run"]["analysis_errors"] == ["g1"]
    assert at(report, "M2", 0.05)["fn"] == 1  # scored 0, still labeled


def test_real_build_on_this_base_has_m2_catalogue():
    build = load_build()
    assert build.catalogues["M2"]["R1"] is True
    # The build mirrors the catalogue's `implemented` flags (no rule id hard-coded: the last ones, R5, R7,
    # R8, R9, R10 and R13, were built in analytics-m2-visual-rules and analytics-m2-text-rules).
    from investwatch_analytics.rules.engine import Catalogue

    assert build.catalogues["M2"] == {s.id: s.implemented for s in Catalogue.load().specs}
    assert all(build.catalogues["M2"].values())  # all 18 rules (19 entries) are built


def test_real_pipeline_scores_an_m2_document():
    text = "Reklama. Zentrovia Dom Maklerski S.A. Zarobisz 12% rocznie na naszym funduszu."
    a = item(1, {"M2": ("positive", {"R3": "fail"})}, text=text, url="https://zentrovia-dm.example.pl/oferta")
    report = run([a], load_build())
    m2 = report["modules"]["M2"]
    assert m2["status"] == "evaluated"
    assert m2["rules"]["R3"]["strict"]["tp"] == 1
    assert at(report, "M2", 0.05)["tp"] == 1


@pytest.mark.parametrize("module", ["M1", "M3"])
def test_real_build_reports_missing_modules_as_not_run(module):
    build = load_build()
    if build.catalogues.get(module) is not None:
        pytest.skip(f"{module} is in this build")
    a = item(1, {module: ("positive", {})}, source_kind="third_party")
    assert run([a], build)["modules"][module]["status"] == "not_run"


def test_pipeline_build_forwards_signals_and_judge(monkeypatch):
    from investwatch_analytics import pipeline
    from investwatch_analytics.evaluation.runner import PipelineBuild

    seen = {}
    monkeypatch.setattr(pipeline, "analyze", lambda doc, **kw: seen.update(kw) or [])
    build = PipelineBuild(catalogue="m2", signals="m1m3", catalogues={}, has_judge=True)
    doc = ScrapedDocument.model_validate(make_doc())
    build.analyze(doc, registry="reg", now=NOW, new_id=str, judge="judge")
    assert (seen["catalogue"], seen["signals"], seen["judge"], seen["registry"]) == ("m2", "m1m3", "judge", "reg")
    seen.clear()
    PipelineBuild("m2", None, {}, False).analyze(doc, registry="reg", now=NOW, new_id=str)
    assert "signals" not in seen and "judge" not in seen  # a build without them gets no unknown argument
