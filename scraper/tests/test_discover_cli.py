"""The `python -m iw_scraper.discover` command: arguments, JSON log lines, exit codes."""

import json
import os
import uuid
from datetime import UTC, datetime

import asyncpg
import pytest

from iw_scraper.discover import main, parse_args


def log_lines(capsys):
    """Every stdout line must be one JSON log record: a stray `print` would fail the parse."""
    return [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]


async def schema_dsn(pool):
    """A DSN that lands on the throwaway schema of the `pool` fixture."""
    schema = await pool.fetchval("SELECT current_schema()")
    return f"{os.environ['IW_TEST_PG_DSN']}?search_path={schema}"


async def seed(pool, hrefs):
    source_id = uuid.uuid4()
    await pool.execute(
        "INSERT INTO sources (id, name, platform, url, source_kind, target_modules, active)"
        " VALUES ($1, 'Alfa', 'web', 'https://alfa.example/', 'firm_own', ARRAY['M2'], true)", source_id,
    )
    await pool.execute(
        "INSERT INTO documents (id, source_id, platform, source_kind, url, fetched_at, text, payload)"
        " VALUES ($1, $2, 'web', 'firm_own', 'https://alfa.example/p', $3, 'tekst', $4::jsonb)",
        uuid.uuid4(), source_id, datetime.now(UTC), json.dumps({"links": [{"href": h} for h in hrefs]}),
    )


def test_defaults_are_a_week_twenty_candidates_and_a_real_run():
    args = parse_args([])

    assert (args.since, args.limit, args.dry_run) == (168.0, 20, False)


def test_options_are_parsed():
    args = parse_args(["--since", "12.5", "--limit", "3", "--dry-run"])

    assert (args.since, args.limit, args.dry_run) == (12.5, 3, True)


@pytest.mark.parametrize("argv", [["--limit", "-1"], ["--since", "0"], ["--since", "-5"], ["--limit", "x"], ["--since", "nan"], ["--since", "inf"],
                  ["--since", "1e9"]])
def test_out_of_range_options_are_refused(argv):
    with pytest.raises(SystemExit) as refused:
        parse_args(argv)

    assert refused.value.code == 2


async def test_a_real_run_inserts_logs_each_candidate_and_one_summary_with_the_counts(pool, capsys):
    await seed(pool, ["https://a.example/", "https://a.example/", "https://b.example/", "https://c.example/"])
    dsn = await schema_dsn(pool)

    code = await main(["--limit", "2"], {"DATABASE_URL": dsn})

    lines = log_lines(capsys)
    summary = lines[-1]["message"]
    assert code == 0
    assert (await pool.fetchval("SELECT count(*) FROM sources WHERE NOT active")) == 2
    assert "links_read=4" in summary and "hosts_considered=3" in summary
    assert "inserted=2" in summary and "skipped_by_cap=1" in summary and "dry_run=False" in summary
    assert any("https://a.example/" in line["message"] and "links=2" in line["message"] for line in lines[:-1])


async def test_a_dry_run_lists_the_candidates_and_writes_nothing(pool, capsys):
    await seed(pool, ["https://a.example/"])
    dsn = await schema_dsn(pool)

    code = await main(["--dry-run"], {"DATABASE_URL": dsn})

    lines = log_lines(capsys)
    assert code == 0
    assert (await pool.fetchval("SELECT count(*) FROM sources")) == 1
    assert any("https://a.example/" in line["message"] for line in lines)
    assert "inserted=0" in lines[-1]["message"] and "dry_run=True" in lines[-1]["message"]


async def test_a_missing_database_url_is_a_logged_error_and_exit_one(capsys):
    code = await main([], {})

    lines = log_lines(capsys)
    assert code == 1
    assert [line["level"] for line in lines] == ["ERROR"]
    assert "DATABASE_URL" in lines[0]["message"]


async def test_an_unreachable_database_exits_one_without_leaking_the_password(capsys):
    code = await main([], {"DATABASE_URL": "postgresql://user:secretpw@127.0.0.1:1/db"})

    out = capsys.readouterr().out
    assert code == 1
    assert "secretpw" not in out
    assert json.loads(out.splitlines()[-1])["level"] == "ERROR"


async def test_a_failing_query_exits_one_with_a_logged_error_and_inserts_nothing(pool, capsys):
    dsn = f"{os.environ['IW_TEST_PG_DSN']}?search_path=iw_no_such_schema"  # connects, but there are no tables

    code = await main([], {"DATABASE_URL": dsn})

    lines = log_lines(capsys)
    assert code == 1
    assert [line["level"] for line in lines] == ["ERROR"] and "discovery failed" in lines[0]["message"]


async def test_a_connection_error_that_echoes_the_dsn_is_redacted_in_the_log(monkeypatch, capsys):
    async def refuse(dsn, **kwargs):
        raise OSError(f"cannot reach {dsn}")

    monkeypatch.setattr(asyncpg, "create_pool", refuse)

    code = await main([], {"DATABASE_URL": "postgresql://user:secretpw@db.example/x"})

    out = capsys.readouterr().out
    assert code == 1 and "secretpw" not in out and "cannot reach postgresql://***@db.example/x" in out


@pytest.mark.parametrize("dsn", ["not a dsn", "postgresql://user:secretpw@[::1/x"])
async def test_a_malformed_dsn_is_a_logged_error_and_exit_one(dsn, capsys):
    code = await main([], {"DATABASE_URL": dsn})

    out = capsys.readouterr().out
    assert code == 1 and "secretpw" not in out and json.loads(out.splitlines()[-1])["level"] == "ERROR"


@pytest.mark.parametrize("error", [OSError("connection dropped"), asyncpg.InterfaceError("pool is closed")])
async def test_a_failure_after_connecting_that_is_not_a_postgres_error_is_logged_and_exits_one(
    pool, monkeypatch, capsys, error
):
    dsn = await schema_dsn(pool)

    async def broken(*args, **kwargs):
        raise error

    monkeypatch.setattr("iw_scraper.discover.discover", broken)

    code = await main([], {"DATABASE_URL": dsn})

    lines = log_lines(capsys)
    assert code == 1
    assert [line["level"] for line in lines] == ["ERROR"] and "discovery failed" in lines[0]["message"]
