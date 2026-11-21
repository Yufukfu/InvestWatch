"""Supervisor and official-register pages are never M1 advertisers, M2 firms or M3 publishers
(change analytics-post-integration-fixes, group 1)."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from conftest import NOW, make_doc
from investwatch_analytics.config import ConfigError, DEFAULT_OFFICIAL_SOURCE_DOMAINS, official_source_domains
from investwatch_analytics.models import ScrapedDocument
from investwatch_analytics.modules.router import route
from investwatch_analytics.pipeline import analyze
from investwatch_analytics.registry import Registry
from investwatch_analytics.rules.engine import Catalogue

SEED = Path(__file__).resolve().parents[1] / "registry" / "seed.csv"
#: The shape of the real KNF public-warnings page: names a registered firm and warns about an unregistered adviser.
WARNINGS = (
    "Lista ostrzeżeń publicznych KNF. EuroTrade Markets – oddział zagraniczny, sprawdź w rejestrze. "
    "Złoty Kapitał Family Office: doradztwo inwestycyjne bez zezwolenia, rekomendujemy kupno akcji WIG20 "
    "i indywidualną strategię dla każdego klienta. Abonament 500 zł miesięcznie."
)


@pytest.fixture(scope="module")
def registry() -> Registry:
    return Registry.from_csv(SEED)


@pytest.fixture(scope="module")
def catalogue() -> Catalogue:
    return Catalogue.load()


def doc(url: str, text: str = WARNINGS, **kw) -> ScrapedDocument:
    base = {"source_kind": "third_party", "platform": "web", "url": url, "text": text}
    base.update(kw)
    return ScrapedDocument.model_validate(make_doc(**base))


def reasons(caplog) -> list[str]:
    return [getattr(r, "reason", None) for r in caplog.records]


class RecordingJudge:
    def __init__(self):
        self.calls = []

    def judge(self, **kw):  # pragma: no cover - must never be reached
        self.calls.append(kw)
        raise AssertionError("an official source must not reach the LLM")


def test_knf_warnings_page_gives_no_finding(registry, catalogue, caplog):
    d = doc("https://www.knf.gov.pl/dla_konsumenta/ostrzezenia_publiczne")
    assert registry.match(d.text, d.url) is not None  # without the guard this page is an M1 candidate
    judge = RecordingJudge()
    with caplog.at_level(logging.INFO):
        assert analyze(d, registry=registry, catalogue=catalogue, now=NOW, judge=judge) == []
    assert "official_source" in reasons(caplog) and judge.calls == []


@pytest.mark.parametrize("url", [
    "https://uknf.gov.pl/komunikat", "https://www.gov.pl/web/finanse", "https://sub.knf.gov.pl/a",
    "https://KNF.GOV.PL./x", "http://gov.pl/",
])
@pytest.mark.parametrize("kind", ["third_party", "unknown", "firm_own"])
def test_official_hosts_route_to_no_module(registry, url, kind):
    r = route(doc(url, source_kind=kind), registry)
    assert (r.module, r.firm_match, r.reason) == (None, None, "official_source")


@pytest.mark.parametrize("url", ["https://knf.gov.pl.example.com/a", "https://fakeknf-gov.pl/a",
                                 "https://notgov.pl/a", "https://gov.pl.evil.example/a"])
def test_look_alike_hosts_are_routed(registry, url):
    assert route(doc(url), registry).reason != "official_source"


def test_unregistered_offer_on_official_host_is_no_m3(registry, catalogue, caplog):
    text = "Rekomendujemy kupno akcji WIG20. Abonament 500 zł miesięcznie, indywidualna strategia."
    with caplog.at_level(logging.INFO):
        assert analyze(doc("https://www.knf.gov.pl/x", text, source_kind="unknown"), registry=registry,
                       catalogue=catalogue, now=NOW) == []
    assert "official_source" in reasons(caplog)


def test_author_profile_on_official_host(registry):
    d = doc("https://www.instagram.com/p/K1/", platform="instagram",
            author={"handle": "@knf_gov_pl", "profile_url": "https://www.knf.gov.pl/o_nas"})
    assert route(d, registry).reason == "official_source"


def test_social_profile_is_not_official(registry):
    d = doc("https://www.instagram.com/p/K1/", platform="instagram",
            author={"handle": "@ola", "profile_url": "https://www.instagram.com/ola"})
    assert route(d, registry).reason != "official_source"


def test_link_to_knf_does_not_make_a_post_official(registry):
    d = doc("https://www.instagram.com/p/A1/", "Polecam EuroTrade Markets, sprawdźcie rejestr.", platform="instagram",
            author={"handle": "@trader_ola"}, links=[{"href": "https://www.knf.gov.pl/podmioty", "text": "rejestr"}])
    assert route(d, registry).module == "M1"


def test_default_list():
    assert DEFAULT_OFFICIAL_SOURCE_DOMAINS == ("knf.gov.pl", "uknf.gov.pl", "gov.pl")
    assert official_source_domains({}) == DEFAULT_OFFICIAL_SOURCE_DOMAINS
    assert official_source_domains({"OFFICIAL_SOURCE_DOMAINS": "  "}) == DEFAULT_OFFICIAL_SOURCE_DOMAINS


def test_env_replaces_the_default(registry, monkeypatch):
    assert official_source_domains({"OFFICIAL_SOURCE_DOMAINS": "ESMA.europa.eu, knf.gov.pl."}) == (
        "esma.europa.eu", "knf.gov.pl")
    monkeypatch.setenv("OFFICIAL_SOURCE_DOMAINS", "esma.europa.eu")
    assert route(doc("https://www.esma.europa.eu/a"), registry).reason == "official_source"
    assert route(doc("https://www.gov.pl/web/finanse"), registry).reason != "official_source"


def test_explicit_argument_wins(registry):
    assert route(doc("https://www.knf.gov.pl/a"), registry, official_domains=()).reason != "official_source"


@pytest.mark.parametrize("bad", ["localhost", "https://knf.gov.pl", "knf.gov.pl/x", "*.gov.pl", "knf.gov.pl:443",
                                 "knf gov.pl"])
def test_bad_entry_is_a_config_error(bad):
    with pytest.raises(ConfigError, match="OFFICIAL_SOURCE_DOMAINS"):
        official_source_domains({"OFFICIAL_SOURCE_DOMAINS": f"gov.pl,{bad}"})
