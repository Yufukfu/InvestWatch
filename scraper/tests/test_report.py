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


# --- queries and entry point (need PostgreSQL: `pool` is skipped without IW_TEST_PG_DSN) ---

import io
import logging
import os
import uuid

import asyncpg
import pytest

from iw_scraper import report as report_module
from iw_scraper.logs import configure_logging
from iw_scraper.report import collect, parse_args, run

START = window_start(NOW, 24)
SECOND = timedelta(seconds=1)
ALFA, BETA, SAMPLE, GAMMA, GHOST = (str(uuid.uuid4()) for _ in range(5))


async def add_source(pool, source_id, name, *, active=True, status=None, last_run_at=None, url="https://s.example.com/"):
    await pool.execute(
        "INSERT INTO sources (id, name, platform, url, source_kind, target_modules, active, last_run_status, last_run_at)"
        " VALUES ($1, $2, 'web', $3, 'firm_own', ARRAY['M3'], $4, $5, $6)",
        uuid.UUID(source_id), name, url, active, status, last_run_at,
    )


async def add_document(pool, source_id, fetched_at, *, platform="web", kind="firm_own", html=False):
    await pool.execute(
        "INSERT INTO documents (id, source_id, platform, source_kind, url, fetched_at, text, html_object_key)"
        " VALUES ($1, $2, $3, $4, $5, $6, 'text', $7)",
        uuid.uuid4(), uuid.UUID(source_id) if source_id else None, platform, kind, URL, fetched_at,
        "raw/key.html" if html else None,
    )


async def add_error(pool, source_id, reason, occurred_at, *, detail=None):
    await pool.execute(
        "INSERT INTO job_errors (id, source_id, reason, detail, occurred_at) VALUES ($1, $2, $3, $4, $5)",
        uuid.uuid4(), uuid.UUID(source_id) if source_id else None, reason, detail, occurred_at,
    )


async def fill(pool):
    await add_source(pool, ALFA, "Alfa", status="ok", last_run_at=NOW, url=URL)
    await add_source(pool, BETA, "Beta", status="partial", last_run_at=NOW)
    await add_source(pool, SAMPLE, "Sample set", active=False)
    await add_source(pool, GAMMA, "Gamma")
    await add_document(pool, ALFA, NOW - timedelta(hours=1), html=True)
    await add_document(pool, ALFA, START - SECOND)
    await add_document(pool, ALFA, NOW - timedelta(hours=48))
    await add_document(pool, BETA, START)
    await add_document(pool, SAMPLE, NOW - timedelta(hours=72))
    await add_document(pool, SAMPLE, NOW - timedelta(hours=73))
    await add_document(pool, None, NOW, platform="x", kind="third_party")
    for _ in range(2):
        await add_error(pool, ALFA, "http_error", NOW - timedelta(hours=2))
    await add_error(pool, ALFA, "timeout", NOW - timedelta(hours=3))
    await add_error(pool, ALFA, "blocked", START - SECOND)
    await add_error(pool, BETA, "boundary", START)
    await add_error(pool, SAMPLE, "parse", NOW, detail=DETAIL)
    await add_error(pool, None, "timeout", NOW)
    await add_error(pool, GHOST, "timeout", NOW)


async def counts(pool) -> list[int]:
    return [await pool.fetchval(f"SELECT count(*) FROM {table}") for table in ("sources", "documents", "job_errors")]


async def test_the_queries_give_the_report_of_the_three_tables(pool):
    await fill(pool)

    async with pool.acquire() as conn:
        built = await collect(conn, hours=24, now=NOW)

    by_id = {entry.id: entry for entry in built.active}
    alfa, beta = by_id[ALFA], by_id[BETA]
    assert (alfa.documents_total, alfa.documents_window, alfa.latest_fetched_at) == (3, 1, NOW - timedelta(hours=1))
    assert (alfa.last_run_status, alfa.last_run_at) == ("ok", NOW)
    assert alfa.errors == {"http_error": 2, "timeout": 1}  # the older `blocked` is outside the window
    assert (beta.documents_total, beta.documents_window, beta.errors) == (1, 1, {"boundary": 1})  # start is inclusive
    [sample] = built.inactive
    assert (sample.id, sample.documents_total, sample.errors) == (SAMPLE, 2, {"parse": 1})
    assert [entry.id for entry in built.never_run] == [GAMMA]
    assert [entry.id for entry in built.no_documents] == [GAMMA]
    assert built.errors == {"boundary": 1, "http_error": 2, "parse": 1, "timeout": 3}
    assert built.unattributed_errors == {"timeout": 2}
    assert built.documents_total == 7
    assert built.by_platform == {"web": 6, "x": 1}
    assert built.by_kind == {"firm_own": 6, "third_party": 1}
    assert built.html_documents == 1


async def test_a_document_and_an_error_without_a_source_are_in_the_totals_and_in_no_entry(pool):
    await add_source(pool, ALFA, "Alfa", status="ok", last_run_at=NOW)
    await add_document(pool, None, NOW, platform="x", kind="third_party", html=True)
    await add_error(pool, None, "parse", NOW)

    async with pool.acquire() as conn:
        built = await collect(conn, hours=24, now=NOW)

    [alfa] = built.active
    assert (alfa.documents_total, alfa.errors) == (0, {})
    assert built.documents_total == 1 and built.by_platform == {"x": 1} and built.html_documents == 1
    assert built.errors == {"parse": 1} and built.unattributed_errors == {"parse": 1}


async def test_the_output_carries_no_detail_and_no_url_from_the_database(pool):
    await fill(pool)

    async with pool.acquire() as conn:
        built = await collect(conn, hours=24, now=NOW)

    for output in (render_table(built), render_json(built)):
        assert DETAIL not in output and "alfa.example.com" not in output and "pw@" not in output


async def test_collecting_writes_no_row_and_its_connection_refuses_a_write(pool):
    await fill(pool)
    before = await counts(pool)
    refused: list[Exception] = []

    class Probe:
        """Tries a write inside the report's own transaction, once, in a savepoint."""

        def __init__(self, conn):
            self.conn = conn

        def transaction(self, **kwargs):
            return self.conn.transaction(**kwargs)

        async def fetch(self, query, *args):
            if not refused:
                try:
                    async with self.conn.transaction():
                        await self.conn.execute("DELETE FROM job_errors")
                    refused.append(AssertionError("the write was accepted"))
                except asyncpg.ReadOnlySQLTransactionError as error:
                    refused.append(error)
            return await self.conn.fetch(query, *args)

    async with pool.acquire() as conn:
        await collect(Probe(conn), hours=24, now=NOW)

    assert [type(error) for error in refused] == [asyncpg.ReadOnlySQLTransactionError]
    assert await counts(pool) == before


@pytest.fixture
def log_lines():
    """The root logger's JSON lines, collected for one test, then the handlers are put back."""
    root = logging.getLogger()
    saved, level = root.handlers[:], root.level
    stream = io.StringIO()
    configure_logging(stream)
    yield lambda: [json.loads(line) for line in stream.getvalue().splitlines()]
    root.handlers[:], root.level = saved, level


async def test_an_unreachable_database_writes_nothing_to_stdout_logs_one_redacted_line_and_fails(capsys, log_lines):
    code = await run([], "postgresql://iw:hunter2@127.0.0.1:1/iw", now=NOW)

    assert code != 0
    assert capsys.readouterr().out == ""
    [line] = log_lines()
    assert line["level"] == "ERROR" and "hunter2" not in json.dumps(line)


async def test_a_missing_database_url_fails_the_same_way(capsys, log_lines):
    code = await run([], None, now=NOW)

    assert code != 0 and capsys.readouterr().out == ""
    assert [line["level"] for line in log_lines()] == ["ERROR"]


@pytest.mark.parametrize("value", ["0", "-3", "abc", "1.5", "", "1_0", "+5", "87601", "1000000000000"])
async def test_an_invalid_window_is_a_usage_error_before_any_connection(value, capsys, monkeypatch):
    async def refuse_to_connect(*args, **kwargs):
        raise AssertionError("connected before the arguments were checked")

    monkeypatch.setattr(report_module.asyncpg, "connect", refuse_to_connect)

    with pytest.raises(SystemExit) as stop:
        await run(["--since", value], "postgresql://iw@127.0.0.1:1/iw", now=NOW)

    captured = capsys.readouterr()
    assert stop.value.code == 2 and captured.out == "" and "--since" in captured.err


def test_the_arguments_default_to_24_hours_and_the_table():
    assert parse_args([]) == (24, False)
    assert parse_args(["--since", "6", "--json"]) == (6, True)


def test_the_longest_window_is_ten_years_and_still_builds_a_report():
    hours, _ = parse_args(["--since", "87600"])

    assert hours == 87600 and report(hours=hours).since.year == 2016


async def test_run_prints_the_table_or_one_json_object_for_the_given_window(pool, capsys):
    await fill(pool)
    schema = await pool.fetchval("SELECT current_schema()")
    dsn = f"{os.environ['IW_TEST_PG_DSN']}?search_path={schema}"

    assert await run(["--since", "24", "--json"], dsn, now=NOW) == 0
    body = json.loads(capsys.readouterr().out)
    assert body["window"]["hours"] == 24 and body["totals"]["documents"] == 7

    assert await run([], dsn, now=NOW) == 0
    table = capsys.readouterr().out
    assert table.startswith("Scraper report, last 24 h") and "Gamma" in table
