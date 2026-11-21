"""Fetching and parsing the KNF lists (spec knf-registry-loader: "Fetching the KNF lists", "Parsing firm records").
Saved snapshots only; the network is never used."""

from __future__ import annotations

import io
import urllib.error

import pytest
from knf_fixtures import FakeFetcher, read

from investwatch_analytics.knf import KnfError
from investwatch_analytics.knf.fetch import LISTS, SUMMARY_URL, HttpFetcher, check_summary, fetch_all, fetch_list
from investwatch_analytics.knf.parse import country_code, parse_page

SOURCES = {s.key: s for s in LISTS}


def _by_name(records, name):
    hits = [r for r in records if name in r.name_lines]
    assert hits, f"{name} not found"
    return hits[0]


# ---- fetching ---------------------------------------------------------------------------------------


def test_fetch_all_reads_every_list_and_stops_at_the_repeated_last_page():
    fetcher = FakeFetcher()
    lists = fetch_all(fetcher)
    assert {k: len(v.records) for k, v in lists.items()} == {
        "brokerage_houses": 28, "banks": 10, "branches": 10, "no_branch": 52,
    }
    nb = SOURCES["no_branch"]
    # pages 1-3 are new, page 4 repeats page 3 (KNF's clamp) and ends the list
    assert [u for u in fetcher.calls if u.startswith(nb.url)] == [nb.page_url(p) for p in (1, 2, 3, 4)]
    assert fetcher.calls[0] == SUMMARY_URL


def test_page_99_clamp_snapshot_equals_the_last_page():
    last = parse_page(read("nobranch_p36.html"), where="no_branch", page=36)
    assert len(last) == 12 and last[0].name_lines == ("WisdomTree Ireland Limited",)


def test_endless_pagination_fails_as_layout_changed():
    class Endless(FakeFetcher):
        def __call__(self, url):
            n = int(url.rsplit("=", 1)[1]) if "?page=" in url else 1
            html = read("dm_p2.html")
            return html.replace("NOBLE Securities S.A.", f"Firma {n} S.A.")

    with pytest.raises(KnfError) as e:
        fetch_list(Endless(), SOURCES["brokerage_houses"], max_pages=100)
    assert e.value.reason == "layout_changed" and "100 pages" in e.value.message


def test_list_no_longer_linked_from_summary():
    summary = read("summary.html").replace("/domy_maklerskie", "/domy_maklerskie_archiwum")
    with pytest.raises(KnfError) as e:
        check_summary(FakeFetcher(summary=summary))
    assert e.value.reason == "list_moved" and "/domy_maklerskie" in e.value.message


def test_summary_links_all_four_lists():
    check_summary(FakeFetcher())


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _fetcher(outcomes):
    sleeps, calls, now = [], [], [0.0]

    def opener(request, timeout):
        calls.append((request.full_url, timeout, request.get_header("User-agent")))
        outcome = outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return _Response(outcome.encode("utf-8"))

    def sleep(s):
        sleeps.append(s)
        now[0] += s

    return HttpFetcher(opener=opener, sleep=sleep, clock=lambda: now[0]), sleeps, calls


def test_page_down_fails_after_three_attempts_with_the_status():
    err = urllib.error.HTTPError("u", 503, "Service Unavailable", {}, None)
    fetcher, sleeps, calls = _fetcher([err, err, err])
    with pytest.raises(KnfError) as e:
        fetcher(SOURCES["banks"].url)
    assert e.value.reason == "fetch_failed"
    assert SOURCES["banks"].url in e.value.message and "HTTP 503" in e.value.message
    assert len(calls) == 3
    assert sleeps == [1, 2]  # backoff between attempts, none after the last


def test_timeout_fails_after_three_attempts():
    fetcher, _, calls = _fetcher([TimeoutError("timed out")] * 3)
    with pytest.raises(KnfError, match="fetch_failed.*TimeoutError"):
        fetcher(SOURCES["banks"].url)
    assert len(calls) == 3


def test_retry_succeeds_on_second_attempt():
    fetcher, _, calls = _fetcher([urllib.error.URLError("reset"), "<html>ok</html>"])
    assert fetcher(SOURCES["banks"].url) == "<html>ok</html>"
    assert len(calls) == 2 and calls[0][1] == 30.0 and "InvestWatch" in calls[0][2]


def test_only_knf_urls_are_fetched():
    fetcher, _, calls = _fetcher(["x"])
    with pytest.raises(KnfError, match="not a KNF URL"):
        fetcher("https://www.knf.gov.pl.evil.example/x")
    assert calls == []


def test_requests_are_throttled():
    now = [0.0]
    sleeps = []

    def opener(request, timeout):
        return _Response(b"x")

    def sleep(s):
        sleeps.append(s)
        now[0] += s

    fetcher = HttpFetcher(opener=opener, sleep=sleep, clock=lambda: now[0], min_interval=0.5)
    fetcher(SOURCES["banks"].url)
    fetcher(SOURCES["banks"].url)
    assert sleeps == [0.5]


def test_page_error_from_fetcher_propagates_and_names_the_url():
    url = SOURCES["branches"].url
    fetcher = FakeFetcher(overrides={url: KnfError("fetch_failed", f"{url}: HTTP 503 after 3 attempts")})
    with pytest.raises(KnfError) as e:
        fetch_all(fetcher)
    assert e.value.reason == "fetch_failed" and url in e.value.message


# ---- parsing ----------------------------------------------------------------------------------------


def test_domestic_brokerage_house_with_former_name():
    records = parse_page(read("dm_p1.html"), where="brokerage_houses")
    ceres = _by_name(records, "CERES DOM INWESTYCYJNY S.A.")
    assert ceres.name_lines == ("CERES DOM INWESTYCYJNY S.A.",)
    assert ceres.former_names == ("EFIX DOM MAKLERSKI S.A.",)


def test_bank_with_brokerage_unit_and_a_stray_strike():
    records = parse_page(read("banks.html"), where="banks")
    pekao = [r for r in records if r.name_lines and r.name_lines[0].startswith("BANK PEKAO")][0]
    assert pekao.name_lines == ("BANK PEKAO S.A. (BANK POLSKA KASA OPIEKI S.A.)", "Biuro Maklerskie PEKAO")
    assert pekao.former_names == ()


def test_strike_spanning_two_lines_is_two_former_names():
    records = parse_page(read("banks.html"), where="banks")
    erste = [r for r in records if r.former_names and r.former_names[0].startswith("SANTANDER")][0]
    assert erste.former_names == ("SANTANDER BANK POLSKA S.A.", "Santander Biuro Maklerskie")
    assert erste.name_lines and not any("SANTANDER" in n.upper() for n in erste.name_lines)


def test_foreign_firm_without_branch():
    records = parse_page(read("nobranch_p2.html"), where="no_branch")
    admiral = _by_name(records, "Admiral Markets AS")
    assert admiral.country_name == "Estonia" and country_code(admiral.country_name) == "EE"
    assert "fi.ee" in admiral.supervisor


def _page(*rows: tuple[str, str]) -> str:
    cells = "".join(f'<tr><th scope="row">{th}</th><td>{td}</td></tr>' for th, td in rows)
    return f'<html><body><div id="entityTable"><table><tbody>{cells}</tbody></table></div></body></html>'


def test_notes_from_snapshot():
    records = parse_page(read("nobranch_p1.html"), where="no_branch")
    assert any("www.50k.trade" in r.notes for r in records)


def test_notes_drop_struck_parts():
    html = _page(("Nazwa podmiotu", "<span>X Markets Ltd</span>"),
                 ("Dodatkowe informacje", "<span>nazwy handlowe: XM <strike>www.old.example</strike><br/>www.new.example</span>"))
    (r,) = parse_page(html, where="t")
    assert "www.new.example" in r.notes and "old.example" not in r.notes and "XM" in r.notes


def test_every_snapshot_record_has_a_name():
    for name in ("banks.html", "dm_p1.html", "dm_p2.html", "branches.html", "nobranch_p1.html",
                 "nobranch_p2.html", "nobranch_p36.html"):
        assert all(r.name_lines for r in parse_page(read(name), where=name)), name


def test_unknown_country_is_none():
    assert country_code("Atlantyda") is None and country_code(None) is None
    assert country_code("Cypr") == "CY"


def test_missing_container_is_layout_changed():
    html = read("dm_p1.html").replace('id="entityTable"', 'id="companies"')
    with pytest.raises(KnfError) as e:
        parse_page(html, where="brokerage_houses", page=1)
    assert e.value.reason == "layout_changed" and "brokerage_houses page 1" in e.value.message


def test_renamed_name_label_is_layout_changed():
    html = read("dm_p1.html").replace(">Nazwa<", ">Firma<")
    with pytest.raises(KnfError) as e:
        parse_page(html, where="brokerage_houses", page=1)
    assert e.value.reason == "layout_changed" and "Nazwa" in e.value.message


def test_tables_outside_the_container_are_ignored():
    html = read("banks.html").replace("<body>", "<body><table><tr><th>Nazwa</th><td>Obca S.A.</td></tr></table>")
    assert all("Obca S.A." not in r.name_lines for r in parse_page(html, where="banks"))


def _blank_first_names(html: str, n: int) -> str:
    marker = '<th class="w-1/2 p-3.5 editor font-semibold" scope="row">Nazwa</th><td class="w-1/2 p-3.5 editor font-semibold"><span>'
    parts = html.split(marker)
    assert len(parts) > n
    for i in range(1, n + 1):
        end = parts[i].index("</span>")
        parts[i] = parts[i][end:]
    return marker.join(parts)


def test_one_malformed_record_is_skipped_and_counted():
    fetcher = FakeFetcher(overrides={SOURCES["brokerage_houses"].url: _blank_first_names(read("dm_p1.html"), 1)})
    result = fetch_list(fetcher, SOURCES["brokerage_houses"])
    assert len(result.records) == 27 and all(r.name_lines for r in result.records)
    assert result.skipped == 1 and result.pages == 2


def test_more_than_five_percent_malformed_fails():
    fetcher = FakeFetcher(overrides={SOURCES["brokerage_houses"].url: _blank_first_names(read("dm_p1.html"), 2)})
    with pytest.raises(KnfError) as e:
        fetch_list(fetcher, SOURCES["brokerage_houses"])
    assert e.value.reason == "layout_changed" and "2 of 28" in e.value.message
