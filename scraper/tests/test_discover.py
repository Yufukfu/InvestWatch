"""Candidate selection: pure functions over stored links (spec `source-discovery`)."""

import pytest

from iw_scraper.discover import FALLBACK_MODULES, Link, clean_url, select_candidates


def link(href, *modules):
    return Link(href=href, modules=tuple(modules))


def urls(selection):
    return [c.url for c in selection.candidates]


# --- clean_url ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "href",
    [
        "https://www.facebook.com/x",
        "https://m.facebook.com/x",
        "https://t.me/channel",
        "https://x.com/u/status/1",
        "https://www.youtube.com/watch?v=1",
        "https://youtu.be/abc",
        "https://bit.ly/abc",
        "https://t.co/abc",
        "https://stats.doubleclick.net/x",
        "https://facebook.com./x",
        "https://t.me./c",
        "https://telegram.me/c",
        "https://wa.me/48123",
        "https://api.whatsapp.com/send",
        "https://www.addthis.com/bookmark",
        "https://www.googletagmanager.com/gtm.js",
    ],
)
def test_denylisted_hosts_and_their_subdomains_are_dropped(href):
    assert clean_url(href) is None


def test_a_host_that_only_ends_like_a_denylisted_one_is_kept():
    assert clean_url("https://notfacebook.com/a") == "https://notfacebook.com/a"


@pytest.mark.parametrize(
    "href",
    [
        "ftp://good.example/a",
        "mailto:a@good.example",
        "javascript:alert(1)",
        "http://127.0.0.1/a",
        "http://[::1]/a",
        "http://10.0.0.1/a",
        "http://127.1/a",
        "https://localhost/",
        "https://localhost./",
        "http://127.0.0.1./a",
        "https://good..example/",
        "https://good.example。evil/",
        "https://ｌｏ.example/",
        "https://intranet/",
        "https://user:pw@good.example/",
        "https://user@good.example/",
        "https://good.example:8443/",
        "http://good.example:443/",
        "https://good.example/a b",
        "https://good.example/a\tb",
        "https://good.example/a\nb",
        "https://good.example/a\x7fb",
        "https://good.example\\@evil.example/",
        "https://good.example/a\\b",
        "",
        "https://",
    ],
)
def test_unsafe_url_shapes_are_dropped(href):
    assert clean_url(href) is None


def test_a_trailing_dot_on_the_host_is_removed():
    assert clean_url("https://Good.example./a") == "https://good.example/a"


def test_default_ports_are_accepted_and_removed():
    assert clean_url("https://good.example:443/a") == "https://good.example/a"
    assert clean_url("http://good.example:80/a") == "http://good.example/a"


def test_fragment_and_tracking_parameters_are_stripped_and_the_rest_kept_as_written():
    assert clean_url("https://good.example/a?utm_source=x&id=7&fbclid=z&UTM_medium=m&gclid=g#top") == (
        "https://good.example/a?id=7"
    )
    assert clean_url("https://good.example/a?q=a%20b&utm_x=1") == "https://good.example/a?q=a%20b"


def test_a_url_with_only_tracking_parameters_loses_its_query_and_an_empty_path_becomes_a_slash():
    assert clean_url("https://GOOD.example?utm_source=x") == "https://good.example/"


# --- select_candidates -------------------------------------------------------------------------------------


def test_one_candidate_per_host_with_the_most_linked_url():
    links = [link("https://good.example/a"), link("https://good.example/b"), link("https://good.example/b"),
             link("https://good.example/c")]

    selection = select_candidates(links, known_hosts=set(), limit=10)

    assert urls(selection) == ["https://good.example/b"]
    assert selection.candidates[0].links == 4  # every link to the host counts for ranking


def test_ties_between_urls_of_one_host_go_to_the_smaller_url():
    links = [link("https://good.example/b"), link("https://good.example/a")]

    assert urls(select_candidates(links, known_hosts=set(), limit=10)) == ["https://good.example/a"]


def test_tracking_variants_of_one_url_count_as_one_url():
    links = [link("https://good.example/b?utm_source=1"), link("https://good.example/b#x"),
             link("https://good.example/a")]

    assert urls(select_candidates(links, known_hosts=set(), limit=10)) == ["https://good.example/b"]


def test_a_known_host_is_skipped_with_www_and_case_folded():
    links = [link("https://www.known.example/a"), link("https://other.example/a"), link("https://Fold.example/a")]

    selection = select_candidates(links, known_hosts={"known.example", "WWW.fold.example"}, limit=10)

    assert urls(selection) == ["https://other.example/a"]


def test_www_and_bare_host_are_one_host():
    links = [link("https://www.good.example/a"), link("https://good.example/b"), link("https://good.example/b")]

    selection = select_candidates(links, known_hosts=set(), limit=10)

    assert urls(selection) == ["https://good.example/b"]


def test_modules_are_the_union_over_every_linking_source():
    links = [link("https://good.example/a", "M2"), link("https://good.example/b", "M3", "M2")]

    assert select_candidates(links, known_hosts=set(), limit=10).candidates[0].modules == ("M2", "M3")


def test_a_host_linked_only_from_orphan_documents_gets_the_fallback_modules():
    selection = select_candidates([link("https://good.example/a")], known_hosts=set(), limit=10)

    assert FALLBACK_MODULES == ("M1",)
    assert selection.candidates[0].modules == ("M1",)


def test_hosts_are_ranked_by_link_count_then_name_and_the_cap_reports_what_it_dropped():
    links = [link("https://c.example/")] * 3 + [link("https://b.example/")] * 2 + [link("https://a.example/")] * 2 + [
        link("https://d.example/")
    ]

    selection = select_candidates(links, known_hosts=set(), limit=2)

    assert urls(selection) == ["https://c.example/", "https://a.example/"]
    assert (selection.hosts_considered, selection.skipped_by_cap) == (4, 2)


def test_a_limit_of_zero_inserts_nothing_and_counts_everything_as_capped():
    selection = select_candidates([link("https://a.example/"), link("https://b.example/")], known_hosts=set(), limit=0)

    assert (urls(selection), selection.skipped_by_cap) == ([], 2)


def test_hosts_considered_counts_only_hosts_that_passed_the_filters_and_are_not_known():
    links = [link("https://t.me/x"), link("http://127.0.0.1/"), link("https://known.example/"),
             link("https://new.example/")]

    selection = select_candidates(links, known_hosts={"known.example"}, limit=10)

    assert (urls(selection), selection.hosts_considered, selection.skipped_by_cap) == (["https://new.example/"], 1, 0)
