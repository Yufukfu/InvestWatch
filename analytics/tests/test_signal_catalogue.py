"""Signal catalogues for M1/M3 on the shared engine (change analytics-m1-m3, task group 1)."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from conftest import make_doc
from investwatch_analytics.models import RuleResult, ScrapedDocument
from investwatch_analytics.preprocessing import preprocess
from investwatch_analytics.registry import Registry
from investwatch_analytics.rules import engine
from investwatch_analytics.rules.engine import Catalogue, CatalogueError, Context, Rule, run_rules
from investwatch_analytics.rules.scoring import capped, sigmoid_score

SEED = Path(__file__).resolve().parents[1] / "registry" / "seed.csv"


def _write(tmp_path, body: str, name: str = "signals.yaml") -> Path:
    p = tmp_path / name
    p.write_text(body, encoding="utf-8")
    return p


# ---- shipped catalogues ------------------------------------------------------------------------


def test_m1_catalogue_ids_and_weights():
    cat = Catalogue.load_module("M1")
    assert [s.id for s in cat.specs] == [f"S1.{i}" for i in range(1, 8)]
    assert isinstance(cat.bias, float)
    assert all(isinstance(s.weight, float) for s in cat.specs)


def test_m3_catalogue_ids_and_weights():
    cat = Catalogue.load_module("M3")
    assert [s.id for s in cat.specs] == [f"S3.{i}" for i in range(1, 9)]
    assert not cat.get("S3.7").implemented
    assert isinstance(cat.bias, float)


def test_m2_catalogue_keeps_default_module():
    assert Catalogue.load().module == "M2"


# ---- loader errors -----------------------------------------------------------------------------

M1_OK = "bias: -1\nrules:\n  - {id: S1.1, name: x, severity: low, weight: 1, implemented: false}\n"


def test_signal_catalogue_minimal_loads(tmp_path):
    cat = Catalogue.load(_write(tmp_path, M1_OK), module="M1")
    assert cat.bias == -1.0 and cat.get("S1.1").weight == 1.0


@pytest.mark.parametrize(
    "body, module, needle",
    [
        ("bias: 0\nrules:\n  - {id: S3.2, name: x, severity: low, weight: 1}\n", "M1", "S3.2"),
        ("bias: 0\nrules:\n  - {id: R1, name: x, severity: low, weight: 1}\n", "M3", "R1"),
        ("rules:\n  - {id: S1.1, name: x, severity: low, legal_basis: null}\n", "M2", "S1.1"),
        ("bias: 0\nrules:\n  - {id: S1.1, name: x, severity: low, weight: high}\n", "M1", "S1.1"),
        ("bias: 0\nrules:\n  - {id: S1.1, name: x, severity: low}\n", "M1", "S1.1"),
        ("bias: 0\nrules:\n  - {id: S1.1, name: x, severity: low, weight: true}\n", "M1", "S1.1"),
        ("rules:\n  - {id: S1.1, name: x, severity: low, weight: 1}\n", "M1", "bias"),
        ("bias: low\nrules:\n  - {id: S1.1, name: x, severity: low, weight: 1}\n", "M1", "bias"),
        ("bias: 0\nrules:\n  - {id: S1.1, name: x, severity: low, weight: 1}\n"
         "  - {id: S1.1, name: y, severity: low, weight: 1}\n", "M1", "S1.1"),
        ("bias: 0\nrules:\n  - {id: S1.1, name: x, severity: low, weight: 1, params: {phrase_patterns: ['(']}}\n",
         "M1", "S1.1"),
        ("bias: 0\nrules:\n  - {id: S1.1, name: x, severity: low, weight: 1, params: {phrase_patern: []}}\n",
         "M1", "phrase_patern"),
        ("bias: 0\nrules:\n  - {id: S1.1, name: x, severity: low, weight: 1, params: {referral_query_keys: ['']}}\n",
         "M1", "referral_query_keys"),
    ],
)
def test_malformed_signal_catalogue(tmp_path, body, module, needle):
    path = _write(tmp_path, body)
    with pytest.raises(CatalogueError) as exc:
        Catalogue.load(path, module=module)
    assert needle in str(exc.value) and str(path) in str(exc.value)


def test_unknown_module_rejected(tmp_path):
    with pytest.raises(CatalogueError):
        Catalogue.load(_write(tmp_path, M1_OK), module="M4")


# ---- evidence fields ---------------------------------------------------------------------------


class _Quote(Rule):
    """Test rule that quotes a fixed string, optionally declaring metadata evidence fields."""

    rule_id = "S1.1"
    quote = ""
    metadata = False

    def evaluate(self, ctx: Context) -> RuleResult:
        return self.result("fail", self.quote, "test")

    def evidence_fields(self, ctx: Context) -> list[str]:
        return engine.metadata_fields(ctx.doc) if self.metadata else super().evidence_fields(ctx)


def _run_quote(monkeypatch, tmp_path, quote: str, metadata: bool) -> RuleResult:
    cls = type("Q", (_Quote,), {"quote": quote, "metadata": metadata})
    monkeypatch.setitem(engine._RULES, "S1.1", cls)
    cat = Catalogue.load(_write(tmp_path, M1_OK.replace("implemented: false", "implemented: true")), module="M1")
    doc = ScrapedDocument.model_validate(make_doc(
        source_kind="third_party", platform="instagram", url="https://www.instagram.com/p/X1/",
        text="Tekst posta.",
        author={"name": "Jan", "handle": "@jan_inwestor", "profile_url": "https://www.instagram.com/jan/"},
        links=[{"href": "https://firma.example.com/?ref=JAN500", "text": "link"}],
    ))
    ctx = Context(doc=doc, pre=preprocess(doc.text), firm_match=None, registry=Registry.from_csv(SEED))
    return run_rules(cat, ctx)[0]


@pytest.mark.parametrize("quote", ["@jan_inwestor", "ref=JAN500", "instagram.com/p/X1", "Jan", "Tekst"])
def test_metadata_quote_accepted_when_declared(monkeypatch, tmp_path, quote):
    res = _run_quote(monkeypatch, tmp_path, quote, metadata=True)
    assert res.result == "fail" and res.evidence == quote


def test_metadata_quote_rejected_for_text_only_rule(monkeypatch, tmp_path):
    res = _run_quote(monkeypatch, tmp_path, "@jan_inwestor", metadata=False)
    assert res.result == "uncertain" and res.evidence is None


def test_quote_in_no_field_becomes_uncertain(monkeypatch, tmp_path):
    res = _run_quote(monkeypatch, tmp_path, "nie ma tego nigdzie", metadata=True)
    assert res.result == "uncertain" and res.evidence is None


def test_metadata_fields_skip_missing_author():
    doc = ScrapedDocument.model_validate(make_doc(text="abc"))
    assert engine.metadata_fields(doc) == ["abc", doc.url]


# ---- score -------------------------------------------------------------------------------------


def _rr(rule_id: str, result: str) -> RuleResult:
    return RuleResult(rule_id=rule_id, name="x", result=result, severity="low", method="rule")


def test_sigmoid_score_uncertain_half(tmp_path):
    cat = Catalogue.load(_write(tmp_path, M1_OK.replace("weight: 1", "weight: 2")), module="M1")
    assert sigmoid_score([_rr("S1.1", "uncertain")], cat) == 0.5


@pytest.mark.parametrize("result, x", [("fail", 1.0), ("pass", 0.0), ("not_applicable", 0.0)])
def test_sigmoid_score_values(tmp_path, result, x):
    cat = Catalogue.load(_write(tmp_path, M1_OK.replace("weight: 1", "weight: 2")), module="M1")
    assert sigmoid_score([_rr("S1.1", result)], cat) == round(1 / (1 + math.exp(-(-1 + 2 * x))), 3)


def test_sigmoid_score_ignores_unknown_ids(tmp_path):
    cat = Catalogue.load(_write(tmp_path, M1_OK), module="M1")
    assert sigmoid_score([_rr("S1.9", "fail")], cat) == round(1 / (1 + math.exp(1)), 3)


def test_sigmoid_score_bounds_and_rounding(tmp_path):
    cat = Catalogue.load(_write(tmp_path, "bias: 50\nrules:\n  - {id: S1.1, name: x, severity: low, weight: 1}\n"),
                         module="M1")
    assert sigmoid_score([], cat) == 1.0
    cat = Catalogue.load(_write(tmp_path, "bias: -800\nrules:\n  - {id: S1.1, name: x, severity: low, weight: 1}\n"),
                         module="M1")
    assert sigmoid_score([], cat) == 0.0


def test_capped():
    assert capped(0.9, 0.4) == 0.4 and capped(0.3, 0.4) == 0.3


def test_existing_m2_rules_still_text_only():
    reg = Registry.from_csv(SEED)
    doc = ScrapedDocument.model_validate(make_doc(text="Reklama. Konto w Alfa Inwestycje."))
    ctx = Context(doc=doc, pre=preprocess(doc.text), firm_match=reg.match(doc.text, doc.url), registry=reg)
    rule = engine._RULES["R1"](Catalogue.load().get("R1"))
    assert rule.evidence_fields(ctx) == [doc.text]
