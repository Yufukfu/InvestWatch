"""Pipeline wiring of embeddings, topic gate and near-dup (analytics-embeddings task groups 7 and 8b)."""

from __future__ import annotations

import logging
from pathlib import Path

import fakeredis
import numpy as np
import pytest

from conftest import NOW, make_doc
from investwatch_analytics.config import GateSettings, NearDupSettings
from investwatch_analytics.embeddings import EmbedOutcome
from investwatch_analytics.models import ScrapedDocument
from investwatch_analytics.neardup import NearDupIndex
from investwatch_analytics.pipeline import Analysis, Gate, analyze, analyze_document
from investwatch_analytics.preprocessing import preprocess
from investwatch_analytics.registry import Registry
from investwatch_analytics.rules.engine import Catalogue

SEED = Path(__file__).resolve().parents[1] / "registry" / "seed.csv"
SOCIAL = {"source_kind": "third_party", "platform": "instagram", "url": "https://www.instagram.com/p/R1/"}
FINFLUENCER = "Konto mam w EuroTrade Markets. Moja grupa: co tydzień mówię, co kupić z akcji WIG20."
RECIPE = "Przepis na sernik babci: twaróg, jajka, cukier i masło. Piec godzinę w 180 stopniach."
VEC = np.ones(8, dtype=np.float32) / np.sqrt(8)


@pytest.fixture(scope="module")
def registry() -> Registry:
    return Registry.from_csv(SEED)


@pytest.fixture(scope="module")
def catalogue() -> Catalogue:
    return Catalogue.load()


class FakeEmbedder:
    model = "bge-m3"

    def __init__(self, outcome: EmbedOutcome | None = None):
        self.outcome = outcome or EmbedOutcome(VEC, "bge-m3", "ok")
        self.calls: list[tuple[str, str]] = []

    def embed(self, text, content_hash):
        self.calls.append((text, content_hash))
        return self.outcome


GATE = Gate.from_settings(GateSettings())


def doc(text=FINFLUENCER, **kw) -> ScrapedDocument:
    raw = make_doc(**{**SOCIAL, "author": {"handle": "@trader_ola"}, "text": text, **kw})
    return ScrapedDocument.model_validate(raw)


def run(d, registry, catalogue, **kw) -> Analysis:
    return analyze_document(d, registry=registry, catalogue=catalogue, now=NOW, **kw)


def log_text(caplog) -> str:
    return "\n".join(f"{r.getMessage()} {r.__dict__}" for r in caplog.records)


# ---- unchanged without the new arguments ------------------------------------------------------


def test_analyze_without_new_arguments_is_unchanged(registry, catalogue):
    findings = analyze(doc(RECIPE), registry=registry, catalogue=catalogue, now=NOW)
    a = run(doc(RECIPE), registry, catalogue)
    assert [f.module for f in findings] == [f.module for f in a.findings]
    assert a.gate is None and a.neardup is None and a.embedding is None


def test_analyze_returns_the_findings_of_analyze_document(registry, catalogue):
    ids = iter(f"{i:08d}-0000-4000-8000-000000000000" for i in range(100))
    ids2 = iter(f"{i:08d}-0000-4000-8000-000000000000" for i in range(100))
    a = analyze(doc(), registry=registry, catalogue=catalogue, now=NOW, new_id=lambda: next(ids), gate=GATE)
    b = run(doc(), registry, catalogue, new_id=lambda: next(ids2), gate=GATE)
    assert [f.model_dump() for f in a] == [f.model_dump() for f in b.findings]


# ---- gate -------------------------------------------------------------------------------------


def test_off_topic_post_dropped_with_reason_and_no_text(registry, catalogue, caplog):
    emb = FakeEmbedder()
    with caplog.at_level(logging.INFO):
        a = run(doc(RECIPE), registry, catalogue, gate=GATE, embedder=emb)
    assert a.findings == [] and a.gate.reason == "off_topic" and not a.gate.passed
    rec = [r for r in caplog.records if getattr(r, "reason", None) == "off_topic"]
    assert rec and rec[0].getMessage() == "document skipped" and rec[0].dict_hits == 0
    assert rec[0].similarity is None and rec[0].embedder is None
    assert "sernik" not in log_text(caplog)
    assert emb.calls == []          # dropped before embedding: no wasted model call


def test_unknown_source_kind_is_gated(registry, catalogue):
    a = run(doc(RECIPE, source_kind="unknown"), registry, catalogue, gate=GATE)
    assert a.findings == [] and a.gate.reason == "off_topic"


def test_investment_post_passes_and_is_routed(registry, catalogue):
    a = run(doc(), registry, catalogue, gate=GATE)
    assert a.gate.passed and [f.module for f in a.findings] == ["M1", "M3"]


def test_firm_page_bypasses_the_gate(registry, catalogue):
    d = doc("Kontakt: ul. Prosta 1, Warszawa. Alfa Inwestycje", source_kind="firm_own", platform="web",
            url="https://alfa-inwestycje.example.com/kontakt")
    a = run(d, registry, catalogue, gate=GATE)
    assert a.gate.reason == "bypassed_firm_own" and [f.module for f in a.findings] == ["M2"]


def test_gate_disabled(registry, catalogue):
    a = run(doc(RECIPE), registry, catalogue, gate=Gate.from_settings(GateSettings(enabled=False)))
    assert a.gate.reason == "gate_disabled"


def test_empty_text_skips_before_gate_and_embedder(registry, catalogue, caplog):
    emb = FakeEmbedder()
    with caplog.at_level(logging.INFO):
        a = run(doc("   "), registry, catalogue, gate=GATE, embedder=emb)
    assert a.findings == [] and a.gate is None and emb.calls == []
    assert any(getattr(r, "reason", None) == "empty_text" for r in caplog.records)


# ---- embedder ---------------------------------------------------------------------------------


def test_embedder_recorded_on_every_finding(registry, catalogue, finding_validator):
    a = run(doc(), registry, catalogue, gate=GATE, embedder=FakeEmbedder())
    assert a.findings and all(f.model.embedder == "bge-m3" for f in a.findings)
    for f in a.findings:
        finding_validator.validate(f.to_contract())


def test_cached_vector_counts_as_used(registry, catalogue):
    a = run(doc(), registry, catalogue, embedder=FakeEmbedder(EmbedOutcome(VEC, "bge-m3", "cached")))
    assert all(f.model.embedder == "bge-m3" for f in a.findings)


@pytest.mark.parametrize("status", ["embed_unavailable", "embed_timeout", "embed_malformed", "breaker_open"])
def test_embedder_failure_gives_null(registry, catalogue, status):
    a = run(doc(), registry, catalogue, gate=GATE, embedder=FakeEmbedder(EmbedOutcome(None, None, status)))
    assert a.findings and all(f.model.embedder is None for f in a.findings)
    assert a.gate.passed


def test_embedder_gets_normalized_text_and_own_hash(registry, catalogue):
    emb = FakeEmbedder()
    d = doc(FINFLUENCER + "   \n\n  ")
    run(d, registry, catalogue, embedder=emb)
    pre = preprocess(d.text)
    assert emb.calls == [(pre.normalized, pre.content_hash)]


def test_firm_page_is_embedded(registry, catalogue):
    emb = FakeEmbedder()
    d = doc(source_kind="firm_own", platform="web", url="https://alfa-inwestycje.example.com/oferta",
            text="Alfa Inwestycje. Zarabiaj 18% rocznie. Inwestowanie wiąże się z ryzykiem.")
    a = run(d, registry, catalogue, gate=GATE, embedder=emb)
    assert emb.calls and a.findings[0].model.embedder == "bge-m3"


def test_no_embedder_gives_null(registry, catalogue):
    a = run(doc(), registry, catalogue)
    assert all(f.model.embedder is None for f in a.findings)


# ---- near-dup ---------------------------------------------------------------------------------

LONG = FINFLUENCER + " " + " ".join(f"Akcja {i} na sesji rośnie o {i} procent." for i in range(40))


def test_neardup_result_returned_and_text_not_in_log(registry, catalogue, caplog):
    idx = NearDupIndex(fakeredis.FakeRedis(decode_responses=True), NearDupSettings())
    first = run(doc(LONG, id="11111111-1111-4111-8111-111111111111"), registry, catalogue, neardup=idx)
    with caplog.at_level(logging.INFO):
        second = run(doc(LONG + " 🚀", id="22222222-2222-4222-8222-222222222222",
                         url="https://www.instagram.com/p/R2/"), registry, catalogue, neardup=idx)
    assert first.neardup.is_original and second.neardup.group_id == "11111111-1111-4111-8111-111111111111"
    assert second.findings and all(f.url == "https://www.instagram.com/p/R2/" for f in second.findings)
    assert "EuroTrade" not in log_text(caplog).replace("finding built", "")


def test_dropped_document_never_enters_the_index(registry, catalogue):
    r = fakeredis.FakeRedis(decode_responses=True)
    a = run(doc(RECIPE * 3), registry, catalogue, gate=GATE, neardup=NearDupIndex(r, NearDupSettings()))
    assert a.neardup is None and r.keys("iw:neardup:*") == []


def test_index_down_does_not_fail_the_document(registry, catalogue):
    class Broken:
        def observe(self, *a, **k):
            return None

    a = run(doc(LONG), registry, catalogue, neardup=Broken())
    assert a.findings and a.neardup is None


def test_neardup_works_without_embeddings(registry, catalogue):
    idx = NearDupIndex(fakeredis.FakeRedis(decode_responses=True), NearDupSettings())
    run(doc(LONG, id="11111111-1111-4111-8111-111111111111"), registry, catalogue, neardup=idx)
    a = run(doc(LONG, id="22222222-2222-4222-8222-222222222222"), registry, catalogue, neardup=idx)
    assert a.neardup.members == 2


# ---- near-dup summary sentence (group 8b) -----------------------------------------------------

from investwatch_analytics.neardup import NearDupResult  # noqa: E402
from investwatch_analytics.pipeline import neardup_sentence  # noqa: E402


def member(n, url="https://www.instagram.com/p/R1/", original=False):
    return NearDupResult("g", original, n, 0.9, None if original else url)


@pytest.mark.parametrize("n,word", [(2, "materiały"), (3, "materiały"), (4, "materiały"), (5, "materiałów"),
                                    (12, "materiałów"), (14, "materiałów"), (22, "materiały"), (25, "materiałów"),
                                    (112, "materiałów"), (102, "materiały")])
def test_sentence_plural(n, word):
    s = neardup_sentence(member(n))
    assert s.endswith(f"(w grupie {n} {word}).") and "https://www.instagram.com/p/R1/" in s


@pytest.mark.parametrize("group", [None, member(1), member(3, original=True), NearDupResult("g", False, 3, 0.9, None)],
                         ids=["no-index", "lone", "original", "no-url"])
def test_no_sentence(group):
    assert neardup_sentence(group) is None


def test_repost_summary_names_the_original(registry, catalogue):
    idx = NearDupIndex(fakeredis.FakeRedis(decode_responses=True), NearDupSettings())
    first = run(doc(LONG, id="11111111-1111-4111-8111-111111111111"), registry, catalogue, neardup=idx)
    second = run(doc(LONG, id="22222222-2222-4222-8222-222222222222", url="https://www.instagram.com/p/R2/"),
                 registry, catalogue, neardup=idx)
    assert all("niemal identyczna" not in (f.summary or "") for f in first.findings)
    for f in second.findings:
        assert f.summary.count("niemal identyczna") == 1 and "https://www.instagram.com/p/R1/" in f.summary
        assert f.summary.endswith("(w grupie 2 materiały).") and f.url == "https://www.instagram.com/p/R2/"
    again = run(doc(LONG, id="11111111-1111-4111-8111-111111111111"), registry, catalogue, neardup=idx)
    assert all("niemal identyczna" not in (f.summary or "") for f in again.findings)


def test_registry_firm_without_vocabulary_passes_the_gate(registry, catalogue):
    a = run(doc("Spotkanie zespołu EuroTrade Markets w piątek o 18."), registry, catalogue, gate=GATE)
    assert a.gate.passed and a.gate.dict_hits == 1


def test_analyze_wrapper_passes_every_argument(registry, catalogue, monkeypatch):
    import investwatch_analytics.pipeline as pipeline

    seen = {}

    def spy(d, **kw):
        seen.update(kw)
        return Analysis()

    monkeypatch.setattr(pipeline, "analyze_document", spy)
    emb, idx = FakeEmbedder(), object()
    assert analyze(doc(), registry=registry, catalogue=catalogue, now=NOW, gate=GATE, embedder=emb,
                   neardup=idx) == []
    assert seen["gate"] is GATE and seen["embedder"] is emb and seen["neardup"] is idx


def test_original_with_a_url_has_no_sentence():
    assert neardup_sentence(NearDupResult("g", True, 3, None, "https://a")) is None
