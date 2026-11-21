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
