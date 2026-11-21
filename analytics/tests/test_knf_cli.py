"""The loader CLI and the safe write (spec knf-registry-loader "Writing the registry"). Saved snapshots only."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from knf_fixtures import FakeFetcher, read

from investwatch_analytics.config import SEED_REGISTRY
from investwatch_analytics.knf import KnfError
from investwatch_analytics.knf import write as write_mod
from investwatch_analytics.knf.__main__ import main
from investwatch_analytics.knf.fetch import LISTS
from investwatch_analytics.registry import Registry

NOW = datetime(2026, 11, 21, 21, 0, tzinfo=timezone.utc)
SOURCES = {s.key: s for s in LISTS}
EMPTY_MANUAL = ["--manual", "absent.csv"]


def _run(tmp_path, *extra, fetcher=None) -> tuple[int, Path, list[dict]]:
    out = tmp_path / "knf.csv"
    code = main(["--out", str(out), "--manual", str(tmp_path / "none.csv"), *extra],
                fetcher=fetcher or FakeFetcher(), now=lambda: NOW)
    return code, out, out


def _logs(capsys) -> list[dict]:
    return [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.startswith("{")]


def test_output_loads_as_a_registry_with_exact_columns_and_sort(tmp_path):
    code, out, _ = _run(tmp_path)
    assert code == 0
    with open(out, encoding="utf-8", newline="") as fh:
        rows = list(csv.reader(fh))
    assert rows[0] == ["id", "name", "aliases", "type", "country", "website_domains", "source_url"]
    registry = Registry.from_csv(out)
    assert len(registry.firms) == 99
    order = [s.type for s in LISTS]
    keys = [(order.index(r[3]), r[1].casefold()) for r in rows[1:]]
    assert [k[0] for k in keys] == sorted(k[0] for k in keys)
    assert all(r[6] in {s.url for s in LISTS} for r in rows[1:])
    assert all(r[0] for r in rows[1:]) and "\r" not in out.read_text(encoding="utf-8")


def test_meta_file_fields(tmp_path):
    code, out, _ = _run(tmp_path)
    meta = json.loads((tmp_path / "knf.meta.json").read_text(encoding="utf-8"))
    assert code == 0 and meta["fetched_at"] == "2026-11-21T21:00:00Z" and meta["loader_version"] == "1.0"
    assert "www.knf.gov.pl" in meta["source"] and meta["firms"] == 99
    assert meta["lists"]["no_branch"] == {"url": SOURCES["no_branch"].url, "type": "foreign_no_branch",
                                          "records": 52, "firms": 51, "pages": 3, "skipped": 0}
    # 51 firms of 52 records: EXT Ltd is also on the branch list and counts there (type precedence)
    assert meta["lists"]["brokerage_houses"]["records"] == 28 and meta["lists"]["banks"]["firms"] == 10
    assert meta["domains"]["curated"] == 0 and meta["domains"]["knf"] > 0


def test_curated_domains_counted_apart_in_meta(tmp_path):
    manual = tmp_path / "manual.csv"
    manual.write_text("name,website_domains,source_url,verified_by_human\n"
                      '"mBANK S.A. – Biuro Maklerskie mBank",mbank.pl,https://www.mbank.pl/,false\n'
                      "XTB S.A.,xtb.com,https://www.xtb.com/pl,true\n", encoding="utf-8")
    out = tmp_path / "knf.csv"
    assert main(["--out", str(out), "--manual", str(manual)], fetcher=FakeFetcher(), now=lambda: NOW) == 0
    meta = json.loads((tmp_path / "knf.meta.json").read_text(encoding="utf-8"))
    assert meta["domains"]["curated"] == 2 and meta["domains"]["curated_unverified"] == 1
    mbank = next(f for f in Registry.from_csv(out).firms if f.name.startswith("mBANK"))
    assert mbank.domains == ("mbank.pl",)


def test_second_run_keeps_ids_and_reports_nothing_new(tmp_path, capsys):
    _run(tmp_path)
    first = (tmp_path / "knf.csv").read_text(encoding="utf-8")
    capsys.readouterr()
    code, _, _ = _run(tmp_path)
    assert code == 0 and (tmp_path / "knf.csv").read_text(encoding="utf-8") == first
    summary = [l for l in _logs(capsys) if l["msg"] == "knf registry written"][0]
    assert summary["added"] == [] and summary["removed"] == [] and summary["firms"] == 99


def test_summary_lists_added_and_removed(tmp_path, capsys):
    _run(tmp_path)
    renamed = read("banks.html").replace("VeloBank S.A.", "NowyBank S.A.")
    fewer = FakeFetcher(overrides={SOURCES["banks"].url: renamed, SOURCES["banks"].page_url(2): renamed})
    capsys.readouterr()
    assert _run(tmp_path, fetcher=fewer)[0] == 0
    summary = [l for l in _logs(capsys) if l["msg"] == "knf registry written"][0]
    assert summary["added"] == ["NowyBank S.A. – Departament Maklerski VeloBank"]
    assert summary["removed"] == ["VeloBank S.A. – Departament Maklerski VeloBank"]


def test_count_dropped_fails_and_leaves_files(tmp_path, capsys):
    _run(tmp_path)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    meta = json.loads((tmp_path / "knf.meta.json").read_text(encoding="utf-8"))
    meta["lists"]["no_branch"]["records"] = 712
    (tmp_path / "knf.meta.json").write_text(json.dumps(meta), encoding="utf-8")
    before["knf.meta.json"] = (tmp_path / "knf.meta.json").read_bytes()
    capsys.readouterr()
    code, _, _ = _run(tmp_path)
    assert code == 1
    err = [l for l in _logs(capsys) if l["msg"] == "knf load failed"][0]
    assert err["reason"] == "count_dropped" and "52" in err["error"] and "712" in err["error"]
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before


def test_accept_drop_writes_anyway(tmp_path):
    _run(tmp_path)
    meta = json.loads((tmp_path / "knf.meta.json").read_text(encoding="utf-8"))
    meta["lists"]["no_branch"]["records"] = 712
    (tmp_path / "knf.meta.json").write_text(json.dumps(meta), encoding="utf-8")
    assert _run(tmp_path, "--accept-drop")[0] == 0


def test_exactly_half_is_not_a_drop():
    fl = {s.key: write_mod.FetchedList(s, [object()] * 5, 0, 1) for s in LISTS}
    write_mod.check_counts(fl, {"lists": {"banks": {"records": 10}}}, accept_drop=False)
    with pytest.raises(KnfError, match="count_dropped"):
        write_mod.check_counts(fl, {"lists": {"banks": {"records": 11}}}, accept_drop=False)


def test_empty_list_fails_even_without_previous_meta(tmp_path, capsys):
    empty = '<html><body><div id="entityTable"></div></body></html>'
    code, out, _ = _run(tmp_path, fetcher=FakeFetcher(overrides={SOURCES["banks"].url: empty}))
    assert code == 1 and not out.exists()
    assert [l for l in _logs(capsys) if l["msg"] == "knf load failed"][0]["reason"] == "count_dropped"


@pytest.mark.parametrize("override,reason", [
    (KnfError("fetch_failed", "x: HTTP 503 after 3 attempts"), "fetch_failed"),
    ('<html><body><div id="companies"></div></body></html>', "layout_changed"),
])
def test_failures_exit_1_with_the_reason_and_write_nothing(tmp_path, capsys, override, reason):
    code, out, _ = _run(tmp_path, fetcher=FakeFetcher(overrides={SOURCES["branches"].url: override}))
    assert code == 1 and not out.exists() and not (tmp_path / "knf.meta.json").exists()
    assert [l for l in _logs(capsys) if l["msg"] == "knf load failed"][0]["reason"] == reason


def test_list_moved_exits_1(tmp_path, capsys):
    summary = read("summary.html").replace("/domy_maklerskie", "/gone")
    code, out, _ = _run(tmp_path, fetcher=FakeFetcher(summary=summary))
    assert code == 1 and not out.exists()
    assert [l for l in _logs(capsys) if l["msg"] == "knf load failed"][0]["reason"] == "list_moved"


def test_interrupted_write_keeps_the_old_file_loadable(tmp_path, monkeypatch):
    _run(tmp_path)
    before = (tmp_path / "knf.csv").read_bytes()

    def boom(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(write_mod.os, "replace", boom)
    renamed = read("banks.html").replace("VeloBank S.A.", "NowyBank S.A.")  # new content, so a write shows
    with pytest.raises(OSError):
        _run(tmp_path, fetcher=FakeFetcher(overrides={SOURCES["banks"].url: renamed,
                                                      SOURCES["banks"].page_url(2): renamed}))
    assert (tmp_path / "knf.csv").read_bytes() == before
    Registry.from_csv(tmp_path / "knf.csv")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["knf.csv", "knf.meta.json"]  # no temp files left


def test_output_that_does_not_load_is_refused(tmp_path, monkeypatch, capsys):
    import investwatch_analytics.knf.__main__ as cli

    monkeypatch.setattr(cli, "render_csv", lambda firms: "id,name,type\nnot-a-uuid,X,brokerage_house\n")
    code, out, _ = _run(tmp_path)
    assert code == 1 and not out.exists()
    assert [l for l in _logs(capsys) if l["msg"] == "knf load failed"][0]["reason"] == "invalid_output"


def test_pipe_in_a_name_never_splits_a_list_cell():
    firm = write_mod.Firm("00000000-0000-4000-8000-000000000001", "A|B Ltd", "foreign_no_branch", "CY",
                          "https://www.knf.gov.pl/x", aliases=["A|B"], domains=[])
    text = write_mod.render_csv([firm])
    assert "A B Ltd" in text and "|" not in text.splitlines()[1].split(",")[2]


def test_the_loader_never_writes_the_seed(tmp_path, monkeypatch, capsys):
    import investwatch_analytics.knf.__main__ as cli

    seed = tmp_path / "seed.csv"  # a copy, so a broken guard can never overwrite the real fixture
    seed.write_bytes(SEED_REGISTRY.read_bytes())
    monkeypatch.setattr(cli, "SEED_REGISTRY", seed)
    code = main(["--out", str(seed), "--manual", "absent.csv"], fetcher=FakeFetcher(), now=lambda: NOW)
    assert code == 1 and seed.read_bytes() == SEED_REGISTRY.read_bytes()
    assert "seed" in [l for l in _logs(capsys) if l["msg"] == "knf load failed"][0]["error"]


def test_previous_ids_are_kept_from_the_previous_csv(tmp_path):
    _run(tmp_path)
    path = tmp_path / "knf.csv"
    text = path.read_text(encoding="utf-8")
    old = next(f for f in Registry.from_csv(path).firms if f.name == "XTB S.A.")
    custom = "0b6d2f1e-3c4a-4b5d-8e6f-7a8b9c0d1e2f"
    path.write_text(text.replace(old.id, custom), encoding="utf-8")
    assert _run(tmp_path)[0] == 0
    assert next(f for f in Registry.from_csv(path).firms if f.name == "XTB S.A.").id == custom
