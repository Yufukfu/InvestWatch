import json
from datetime import UTC, datetime, timedelta

from iw_scraper.report import Rows, build_report, render_json, render_table, window_start

NOW = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)
DETAIL = "secret detail text"
URL = "https://user:pw@alfa.example.com/page"


def source(source_id="s1", *, name="Alfa", active=True, platform="web", kind="firm_own", status="ok",
           last_run_at=NOW, total=3, window=1, latest=NOW):
    return {
        "id": source_id, "name": name, "platform": platform, "source_kind": kind, "active": active,
        "last_run_status": status, "last_run_at": last_run_at,
        "documents_total": total, "documents_window": window, "latest_fetched_at": latest,
    }


def errors(source_id, reason, count):
    return {"source_id": source_id, "reason": reason, "count": count}


def documents(platform="web", kind="firm_own", total=3, with_html=3):
    return {"platform": platform, "source_kind": kind, "total": total, "with_html": with_html}


def report(*, sources=(), errs=(), docs=(), hours=24):
    return build_report(Rows(sources=list(sources), errors=list(errs), documents=list(docs)), hours=hours, now=NOW)


def test_the_window_starts_the_given_hours_before_now():
    assert window_start(NOW, 24) == datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
    assert window_start(NOW, 1) == NOW - timedelta(hours=1)


def test_a_source_shows_its_counts_and_the_errors_of_the_window():
    built = report(
        sources=[source(total=3, window=1)],
        errs=[errors("s1", "http_error", 2), errors("s1", "timeout", 1)],
        docs=[documents(total=3)],
    )

    [entry] = built.active
    assert (entry.id, entry.name, entry.platform, entry.source_kind) == ("s1", "Alfa", "web", "firm_own")
    assert (entry.documents_total, entry.documents_window) == (3, 1)
    assert entry.errors == {"http_error": 2, "timeout": 1}
    assert built.errors == {"http_error": 2, "timeout": 1}
    assert built.never_run == () and built.no_documents == ()


def test_a_source_that_never_ran_is_listed_as_never_run_and_without_documents():
    built = report(sources=[source("s2", name="Beta", status=None, last_run_at=None, total=0, window=0, latest=None)])

    assert [(s.id, s.name) for s in built.never_run] == [("s2", "Beta")]
    assert [(s.id, s.name) for s in built.no_documents] == [("s2", "Beta")]


def test_a_source_that_ran_without_documents_is_only_without_documents():
    built = report(sources=[source("s3", total=0, window=0, latest=None)])

    assert built.never_run == ()
    assert [s.id for s in built.no_documents] == ["s3"]


def test_inactive_sources_are_apart_and_not_counted_as_never_run_or_without_documents():
    built = report(
        sources=[
            source("sample", name="Sample set", active=False, status=None, last_run_at=None, total=5, window=0),
            source("idle", name="Idle", active=False, status=None, last_run_at=None, total=0, window=0, latest=None),
        ],
        docs=[documents(total=5, with_html=0)],
    )

    assert built.active == ()
    assert [(s.id, s.documents_total) for s in built.inactive] == [("sample", 5), ("idle", 0)]
    assert built.never_run == () and built.no_documents == ()


def test_an_error_of_an_inactive_source_is_in_its_entry_and_the_totals_only():
    built = report(
        sources=[source("off", active=False), source("on")],
        errs=[errors("off", "blocked", 2)],
    )

    [off] = built.inactive
    assert off.errors == {"blocked": 2}
    assert built.active[0].errors == {}
    assert built.errors == {"blocked": 2}
    assert built.unattributed_errors == {}


def test_errors_of_an_unknown_or_missing_source_are_unattributed_and_in_the_totals():
    built = report(
        sources=[source("s1")],
        errs=[errors("ghost", "timeout", 2), errors(None, "timeout", 1), errors(None, "parse", 4), errors("s1", "timeout", 1)],
    )

    assert built.unattributed_errors == {"timeout": 3, "parse": 4}
    assert built.errors == {"timeout": 4, "parse": 4}
    assert built.active[0].errors == {"timeout": 1}


def test_totals_count_documents_by_platform_and_kind_and_the_html_share():
    built = report(docs=[
        documents("web", "firm_own", total=4, with_html=3),
        documents("web", "third_party", total=2, with_html=0),
        documents("x", "third_party", total=2, with_html=1),
    ])

    assert built.documents_total == 8
    assert built.by_platform == {"web": 6, "x": 2}
    assert built.by_kind == {"firm_own": 4, "third_party": 4}
    assert built.html_documents == 4
    assert built.html_share == 0.5


def test_an_empty_database_gives_zero_totals_and_no_share():
    built = report()

    assert built.documents_total == 0 and built.html_documents == 0
    assert built.by_platform == {} and built.by_kind == {} and built.errors == {}
    assert built.html_share is None
    assert "n/a" in render_table(built)
    assert json.loads(render_json(built))["totals"]["html_share"] is None


def test_both_formats_carry_the_window_and_the_last_run_note_and_no_success_figure():
    built = report(sources=[source()], errs=[errors("s1", "timeout", 1)], docs=[documents()], hours=6)

    table = render_table(built)
    body = json.loads(render_json(built))

    assert "last run only" in table and "last 6 h" in table
    assert body["window"] == {"hours": 6, "since": "2026-11-21T06:00:00Z", "until": "2026-11-21T12:00:00Z"}
    assert "last run only" in body["note"]
    assert "success" not in table.lower() and "success" not in render_json(built).lower()


def test_neither_format_shows_error_detail_or_a_url():
    built = report(
        sources=[source()],
        errs=[{"source_id": "s1", "reason": "timeout", "count": 1, "detail": DETAIL, "url": URL}],
        docs=[{**documents(), "url": URL}],
    )

    for output in (render_table(built), render_json(built)):
        assert DETAIL not in output and "alfa.example.com" not in output and "pw@" not in output


def test_the_json_output_is_one_object_with_the_figures_of_the_table():
    built = report(sources=[source()], errs=[errors("s1", "timeout", 1)], docs=[documents(total=3, with_html=3)])

    body = json.loads(render_json(built))

    assert body["sources"][0] == {
        "id": "s1", "name": "Alfa", "platform": "web", "source_kind": "firm_own",
        "last_run_status": "ok", "last_run_at": "2026-11-21T12:00:00Z",
        "documents_total": 3, "documents_window": 1, "latest_fetched_at": "2026-11-21T12:00:00Z",
        "errors": {"timeout": 1},
    }
    assert body["totals"]["errors"] == {"timeout": 1}
    assert body["totals"]["html_share"] == 1.0
    assert render_json(built).count("\n") <= 1
