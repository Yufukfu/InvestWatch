"""Curated domains for domestic firms (spec knf-registry-loader "Firm domains", design decision 6). No network."""

from __future__ import annotations

from pathlib import Path

import pytest
from knf_fixtures import FakeFetcher

from investwatch_analytics.knf import KnfError
from investwatch_analytics.knf.build import build, load_manual
from investwatch_analytics.knf.fetch import fetch_all

MANUAL = Path(__file__).resolve().parents[1] / "registry" / "knf_domains_manual.csv"
HEADER = "name,website_domains,source_url,verified_by_human\n"


@pytest.fixture(scope="module")
def snapshot():
    return fetch_all(FakeFetcher())


def _write(tmp_path, *rows: str) -> Path:
    p = tmp_path / "manual.csv"
    p.write_text(HEADER + "".join(r + "\n" for r in rows), encoding="utf-8")
    return p


def _firm(firms, name):
    return next(f for f in firms if f.name == name)


def test_curated_domain_merged_and_counted_as_unverified(tmp_path, snapshot):
    rows = load_manual(_write(tmp_path, '"mBANK S.A. – Biuro Maklerskie mBank",mbank.pl,https://www.mbank.pl/,false'))
    firms, report = build(snapshot, manual=rows)
    assert _firm(firms, "mBANK S.A. – Biuro Maklerskie mBank").domains == ["mbank.pl"]
    assert report.curated == [("mBANK S.A. – Biuro Maklerskie mBank", "mbank.pl", False)]


def test_verified_flag_is_kept(tmp_path, snapshot):
    rows = load_manual(_write(tmp_path, "XTB S.A.,xtb.com,https://www.xtb.com/pl,true"))
    _, report = build(snapshot, manual=rows)
    assert report.curated == [("XTB S.A.", "xtb.com", True)]


def test_curated_domain_wins_over_a_foreign_firm_listing_it(tmp_path, snapshot):
    # XTB Ltd (Cyprus, no branch) lists www.xtb.com in its KNF notes; the curated row gives it to XTB S.A.
    firms, report = build(snapshot, manual=load_manual(_write(tmp_path, "XTB S.A.,xtb.com,https://www.xtb.com/pl,false")))
    assert _firm(firms, "XTB S.A.").domains == ["xtb.com"] and _firm(firms, "XTB Ltd").domains == []
    assert ("xtb.com", "shared") in report.dropped_domains


def test_stale_manual_row_fails(tmp_path, snapshot):
    rows = load_manual(_write(tmp_path, "NIEISTNIEJĄCY DOM MAKLERSKI S.A.,example.pl,https://example.pl/,false"))
    with pytest.raises(KnfError) as e:
        build(snapshot, manual=rows)
    assert e.value.reason == "manual_row" and "NIEISTNIEJĄCY DOM MAKLERSKI S.A." in e.value.message


@pytest.mark.parametrize("row,fragment", [
    ("XTB S.A.,xtb.com,https://www.xtb.com/pl,maybe", "verified_by_human"),
    ("XTB S.A.,xtb.com,http://www.xtb.com/pl,false", "https"),
    ("XTB S.A.,xtb.com,https://evil.example/xtb,false", "not on"),
    ("XTB S.A.,facebook.com,https://www.facebook.com/xtb,false", "social"),
    ("XTB S.A.,localhost,https://localhost/,false", "not a domain"),
    ("XTB S.A.,,https://www.xtb.com/,false", "no domains"),
    (",xtb.com,https://www.xtb.com/,false", "empty name"),
])
def test_invalid_manual_rows_fail_at_load(tmp_path, row, fragment):
    with pytest.raises(KnfError) as e:
        load_manual(_write(tmp_path, row))
    assert e.value.reason == "manual_row" and fragment in e.value.message and "manual.csv:2" in e.value.message


def test_missing_column_fails(tmp_path):
    p = tmp_path / "manual.csv"
    p.write_text("name,website_domains\nXTB S.A.,xtb.com\n", encoding="utf-8")
    with pytest.raises(KnfError, match=r"manual_row: .*manual\.csv: missing column\(s\) source_url, verified_by_human"):
        load_manual(p)


def test_missing_file_is_no_rows(tmp_path):
    assert load_manual(tmp_path / "absent.csv") == []


def test_committed_manual_file_is_valid_and_names_registry_firms(snapshot):
    rows = load_manual(MANUAL)
    assert rows, "registry/knf_domains_manual.csv is empty"
    firms, report = build(snapshot, manual=rows)
    domestic = {f.name for f in firms if f.type in ("brokerage_house", "brokerage_bank")}
    assert {r.name for r in rows} <= domestic
    assert len(report.curated) == sum(len(r.domains) for r in rows)


# ---- review fixes (group 4) -------------------------------------------------------------------------

PEKAO_BANK = '"BANK PEKAO S.A. (BANK POLSKA KASA OPIEKI S.A.) – Biuro Maklerskie PEKAO"'


def test_one_domain_for_two_firms_fails(tmp_path):
    with pytest.raises(KnfError) as e:
        load_manual(_write(tmp_path, "PEKAO INVESTMENT BANKING S.A.,pekao.com.pl,https://www.pekao.com.pl/,false",
                           f"{PEKAO_BANK},pekao.com.pl,https://www.pekao.com.pl/,false"))
    assert e.value.reason == "manual_row" and "pekao.com.pl overlaps" in e.value.message and "manual.csv:3" in e.value.message


def test_nested_domain_for_another_firm_fails(tmp_path):
    with pytest.raises(KnfError, match="ib.pekao.com.pl overlaps pekao.com.pl"):
        load_manual(_write(tmp_path, f"{PEKAO_BANK},pekao.com.pl,https://www.pekao.com.pl/,false",
                           "PEKAO INVESTMENT BANKING S.A.,ib.pekao.com.pl,https://ib.pekao.com.pl/,false"))


def test_repeated_firm_row_fails(tmp_path):
    with pytest.raises(KnfError, match="repeats the row at .*manual.csv:2"):
        load_manual(_write(tmp_path, "XTB S.A.,xtb.com,https://www.xtb.com/pl,true",
                           "xtb s.a.,xtb.pl,https://www.xtb.pl/,false"))


def test_two_domains_of_one_firm_are_fine(tmp_path):
    (row,) = load_manual(_write(tmp_path, "XTB S.A.,xtb.com|xtb.pl,https://www.xtb.com/pl,false"))
    assert row.domains == ("xtb.com", "xtb.pl")


def test_curated_count_only_holds_domains_that_reach_the_csv(tmp_path, snapshot):
    # cysec.gov.cy is a supervisor site in the snapshots, so it is dropped from the firm and not counted.
    rows = load_manual(_write(tmp_path, "XTB S.A.,xtb.com|cysec.gov.cy,https://www.xtb.com/pl,false"))
    firms, report = build(snapshot, manual=rows)
    assert _firm(firms, "XTB S.A.").domains == ["xtb.com"]
    assert report.curated == [("XTB S.A.", "xtb.com", False)]


@pytest.mark.parametrize("domain", ["com.pl", "192.168.0.1", "-x.pl", "x..pl", "a_b.pl", "xn--.pl"])
def test_bad_hosts_rejected(tmp_path, domain):
    with pytest.raises(KnfError, match="is not a domain"):
        load_manual(_write(tmp_path, f"XTB S.A.,{domain},https://www.xtb.com/,false"))


@pytest.mark.parametrize("url", [r"https://evil.pl\@xtb.com/", "https://user@xtb.com/"])
def test_source_url_with_userinfo_or_backslash_rejected(tmp_path, url):
    with pytest.raises(KnfError, match="backslash or userinfo"):
        load_manual(_write(tmp_path, f"XTB S.A.,xtb.com,{url},false"))
