"""Link-host registry match, publisher identity and advertiser (change analytics-m1-m3, task group 2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from conftest import make_doc
from investwatch_analytics.models import Link, ScrapedDocument
from investwatch_analytics.modules.advertiser import (
    MAX_LEN,
    build_advertiser,
    normalize_handle,
    page_host,
    publisher_firm,
)
from investwatch_analytics.registry import Firm, Registry

SEED = Path(__file__).resolve().parents[1] / "registry" / "seed.csv"
ALFA = "facc6bd1-c728-5348-90a4-011b0972fea9"
EURO = "2d7456b6-f7b5-52f2-a039-64e250001e24"


@pytest.fixture(scope="module")
def registry() -> Registry:
    return Registry.from_csv(SEED)


def doc(**kw) -> ScrapedDocument:
    base = {"source_kind": "third_party", "platform": "instagram", "url": "https://www.instagram.com/p/X1/"}
    base.update(kw)
    return ScrapedDocument.model_validate(make_doc(**base))


# ---- link hosts --------------------------------------------------------------------------------


def test_referral_link_matches_firm(registry):
    href = "https://eurotrade-markets.example.com/pl/register?ref=X"
    m = registry.match_links([Link(href=href)])
    assert m is not None and m.firm.id == EURO and m.confidence == 0.9 and m.method == "link" and m.evidence == href


def test_link_subdomain_matches(registry):
    m = registry.match_links([Link(href="https://app.alfa-inwestycje.example.com/x")])
    assert m is not None and m.firm.id == ALFA


@pytest.mark.parametrize("href", ["not a url", "ftp://alfa-inwestycje.example.com/", "javascript:alert(1)",
                                  "https://", "http://[::1", "https://notalfa-inwestycje.example.com/"])
def test_bad_or_foreign_links_skipped(registry, href):
    assert registry.match_links([Link(href=href)]) is None


def test_first_matching_link_wins(registry):
    links = [Link(href="nope"), Link(href="https://bank-przykladowy.example.com/"),
             Link(href="https://alfa-inwestycje.example.com/")]
    assert registry.match_links(links).firm.name.startswith("Bank")


def test_social_link_never_matches():
    reg = Registry([_firm("Alfa Inwestycje", ("instagram.com",))])
    assert reg.match_links([Link(href="https://www.instagram.com/alfa/")]) is None


@pytest.mark.parametrize("href", [r"https://evil.example.com\@alfa-inwestycje.example.com/x",
                                  r"https://evil.example.com\x@alfa-inwestycje.example.com/"])
def test_backslash_authority_is_not_a_firm_link(registry, href):
    assert registry.match_links([Link(href=href)]) is None


def test_backslash_profile_url_is_not_the_firm(registry):
    d = doc(text="x", author={"handle": "@kto", "profile_url": r"https://evil.example.com\@alfa-inwestycje.example.com/"})
    assert publisher_firm(d, registry) is None


# ---- publisher identity ------------------------------------------------------------------------


def test_normalize_handle():
    assert normalize_handle("@Alfa_Inwestycje") == "alfainwestycje"
    assert normalize_handle("Bank Przykładowy") == "bankprzykladowy"
    assert normalize_handle("@@--") == ""


def test_publisher_by_handle(registry):
    d = doc(text="Konto w Alfa Inwestycje.", author={"handle": "@alfainwestycje"})
    assert publisher_firm(d, registry).id == ALFA


def test_publisher_by_handle_of_alias(registry):
    d = doc(text="x", author={"handle": "@alfa_inwestycje_dm"})
    assert publisher_firm(d, registry).id == ALFA


def test_fan_account_is_not_the_firm(registry):
    d = doc(text="x", author={"handle": "@alfa_inwestycje_fan"})
    assert publisher_firm(d, registry) is None


def test_empty_handle_is_not_a_firm(registry):
    assert publisher_firm(doc(text="x", author={"handle": "@"}), registry) is None


def test_publisher_by_profile_host(registry):
    d = doc(text="x", author={"handle": "@kto", "profile_url": "https://blog.alfa-inwestycje.example.com/o-nas"})
    assert publisher_firm(d, registry).id == ALFA


def test_publisher_by_page_host(registry):
    d = doc(platform="web", url="https://alfa-inwestycje.example.com/blog/1", text="x")
    assert publisher_firm(d, registry).id == ALFA


def test_social_page_host_is_not_a_publisher(registry):
    assert publisher_firm(doc(text="Alfa Inwestycje"), registry) is None


def test_malformed_profile_url_ignored(registry):
    d = doc(text="x", author={"handle": "@kto", "profile_url": "javascript:alert(1)"})
    assert publisher_firm(d, registry) is None


# ---- advertiser --------------------------------------------------------------------------------


def test_advertiser_from_author(registry):
    d = doc(text="x", author={"name": "Jan Inwestor", "handle": "@inwestor_jan",
                              "profile_url": "https://www.instagram.com/inwestor_jan/", "followers": 3})
    a = build_advertiser(d, registry)
    assert a.model_dump() == {"name": "Jan Inwestor", "handle": "@inwestor_jan",
                              "profile_url": "https://www.instagram.com/inwestor_jan/", "website": None,
                              "in_registry": False, "on_warning_list": None}


def test_advertiser_handle_only(registry):
    a = build_advertiser(doc(text="x", author={"handle": "@sygnaly_vip"}), registry)
    assert a.name == "@sygnaly_vip" and a.website is None


def test_advertiser_from_page_host(registry):
    d = doc(platform="web", source_kind="unknown", url="https://www.ZlotyKapital-fo.example.com/oferta", text="x")
    a = build_advertiser(d, registry)
    assert a.name == "ZlotyKapital-fo.example.com" and a.website == "https://ZlotyKapital-fo.example.com/"
    assert a.in_registry is False and a.on_warning_list is None and a.handle is None


def test_empty_author_counts_as_no_author(registry):
    d = doc(platform="web", url="https://blog.example.com/a", text="x", author={"name": "  "})
    a = build_advertiser(d, registry)
    assert a.name == "blog.example.com" and a.website == "https://blog.example.com/"


@pytest.mark.parametrize("bad", ["javascript:alert(1)", "https://x.example.com/a b", "/relative"])
def test_malformed_profile_url_becomes_null(registry, bad):
    a = build_advertiser(doc(text="x", author={"handle": "@kto", "profile_url": bad}), registry)
    assert a.profile_url is None and a.handle == "@kto"


def test_long_strings_are_cut(registry):
    a = build_advertiser(doc(text="x", author={"name": "  " + "J" * 5000, "handle": "@" + "h" * 5000}), registry)
    assert a.name == "J" * MAX_LEN and len(a.handle) == MAX_LEN and MAX_LEN == 200


def test_over_long_profile_url_becomes_null(registry):
    a = build_advertiser(doc(text="x", author={"handle": "@kto",
                                                "profile_url": "https://www.instagram.com/" + "a" * 300}), registry)
    assert a.profile_url is None


def test_backslash_profile_url_becomes_null(registry):
    a = build_advertiser(doc(text="x", author={"handle": "@kto",
                                                "profile_url": r"https://evil.example.com\@www.instagram.com/x"}), registry)
    assert a.profile_url is None


def test_empty_page_host_never_fails_the_advertiser(registry):
    a = build_advertiser(doc(platform="web", url="https://www./", text="x", author=None), registry)
    assert a.website is None and a.name is None and a.in_registry is False


def test_firm_publisher_in_registry(registry):
    a = build_advertiser(doc(text="x", author={"handle": "@alfainwestycje"}), registry)
    assert a.in_registry is True


def test_page_host_keeps_original_case_and_drops_www():
    assert page_host("https://www.Blog.Example.com:8443/x") == "Blog.Example.com"
    assert page_host("https://user@host.example.com/") == "host.example.com"


def _firm(name: str, domains: tuple[str, ...] = ()) -> Firm:
    return Firm(id=ALFA, name=name, type="brokerage_house", country="PL", aliases=(), domains=domains,
                source_url=None)


def test_punctuation_only_name_never_matches_empty_handle():
    reg = Registry([_firm("&&")])
    assert publisher_firm(doc(text="x", author={"handle": "@--"}), reg) is None


def test_social_domain_in_registry_is_not_a_publisher():
    reg = Registry([_firm("Alfa Inwestycje", ("instagram.com",))])
    d = doc(text="x", author={"handle": "@kto", "profile_url": "https://www.instagram.com/kto/"})
    assert publisher_firm(d, reg) is None


def test_social_page_host_with_social_domain_in_registry():
    reg = Registry([_firm("Alfa Inwestycje", ("instagram.com",))])
    assert publisher_firm(doc(text="x"), reg) is None
