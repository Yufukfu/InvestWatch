"""An M3-only document needs an offer signal; service vocabulary alone gives no finding
(change analytics-post-integration-fixes, group 2)."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from conftest import NOW, make_doc
from investwatch_analytics.models import RuleResult, ScrapedDocument
from investwatch_analytics.modules import m3
from investwatch_analytics.pipeline import analyze
from investwatch_analytics.preprocessing import preprocess
from investwatch_analytics.registry import Registry
from investwatch_analytics.rules.engine import Catalogue, Context, run_rules

SEED = Path(__file__).resolve().parents[1] / "registry" / "seed.csv"
BLOG = "72acbb3b-3546-5c9b-9b26-2b29f69ccce9"
#: The shape of the EY negative control: an unregistered name, service vocabulary, a Polish host, no offer.
EY_LIKE = ("Family office to model zarządzania majątkiem rodziny. Nasi eksperci łączą doradztwo inwestycyjne, "
           "prawne i podatkowe. Dowiedz się więcej o naszym podejściu.")


@pytest.fixture(scope="module")
def registry() -> Registry:
    return Registry.from_csv(SEED)


@pytest.fixture(scope="module")
def catalogue() -> Catalogue:
    return Catalogue.load()


def page(text: str, url: str = "https://www.doradcy-rodzinni.pl/family-office") -> ScrapedDocument:
    return ScrapedDocument.model_validate(make_doc(source_kind="unknown", platform="web", url=url, text=text))


def reasons(caplog) -> list[str]:
    return [getattr(r, "reason", None) for r in caplog.records]


def rr(rule_id: str, result: str) -> RuleResult:
    return RuleResult(rule_id=rule_id, name=rule_id, result=result, severity="medium")


def test_ey_like_page_gives_no_finding(registry, catalogue, caplog):
    d = page(EY_LIKE)
    ctx = Context(doc=d, pre=preprocess(d.text), firm_match=None, registry=registry)
    rules = {r.rule_id: r.result for r in run_rules(Catalogue.load_module("M3"), ctx)}
    # the case of the 2026-11-22 run: S3.1, S3.2 and S3.6 present, no offer signal
    assert (rules["S3.1"], rules["S3.2"], rules["S3.6"]) == ("fail", "fail", "fail")
    assert all(rules[s] == "pass" for s in ("S3.3", "S3.4", "S3.5", "S3.8"))
    with caplog.at_level(logging.INFO):
        assert analyze(d, registry=registry, catalogue=catalogue, now=NOW) == []
    assert "no_signals" in reasons(caplog)


def test_educational_blog_gives_no_finding(mock_documents, registry, catalogue, caplog):
    raw = next(x for x in mock_documents if x["id"] == BLOG)
    with caplog.at_level(logging.INFO):
        assert analyze(ScrapedDocument.model_validate(raw), registry=registry, catalogue=catalogue, now=NOW) == []
    assert "no_signals" in reasons(caplog)


@pytest.mark.parametrize("text", [
    "Family office i doradztwo inwestycyjne. Rekomendujemy kupno akcji WIG20.",           # S3.4
    "Family office i doradztwo inwestycyjne. Abonament 500 zł miesięcznie.",              # S3.5
    "Family office. Kupuj bitcoina teraz, sprzedaj na szczycie.",                         # S3.8
])
def test_offer_signal_still_gives_a_finding(registry, catalogue, text):
    findings = analyze(page(text), registry=registry, catalogue=catalogue, now=NOW)
    assert [f.module for f in findings] == ["M3"], text


@pytest.mark.parametrize("sid", ["S3.3", "S3.4", "S3.5", "S3.8"])
@pytest.mark.parametrize("result", ["fail", "uncertain"])
def test_each_offer_signal_counts(sid, result):
    assert m3.has_advisory([rr("S3.1", "fail"), rr("S3.2", "fail"), rr("S3.6", "fail"), rr(sid, result)])


@pytest.mark.parametrize("result", ["fail", "uncertain"])
def test_vocabulary_and_context_are_no_offer(result):
    assert not m3.has_advisory([rr("S3.1", result), rr("S3.2", result), rr("S3.6", result), rr("S3.7", result),
                                rr("S3.3", "pass"), rr("S3.4", "not_applicable")])


def test_offer_set():
    assert m3.OFFER == ("S3.3", "S3.4", "S3.5", "S3.8") and m3.ADVISORY == m3.OFFER
