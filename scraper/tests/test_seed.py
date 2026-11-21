import asyncio
import os
from urllib.parse import urlsplit

import pytest

from iw_scraper.app import allowed_urls
from iw_scraper.fetch import FetchFailure
from iw_scraper.pgstore import PgSourceStore
from iw_scraper.types import Reason

from iw_scraper import seed as seed_module
from iw_scraper.seed import (
    _LOCK_KEY,
    KNF_URL,
    SEEDS_DIR,
    SeedEntry,
    SeedError,
    cron_from,
    load_seed_dir,
    main,
    seed_all,
    seed_knf,
    seed_sources,
)

ENTRIES = load_seed_dir(SEEDS_DIR)
WEB_ENTRIES = [entry for entry in ENTRIES if entry.platform == "web"]  # only these go through the web fetch path (`collectable()`)


def stored(rows) -> list[tuple]:
    return sorted((r["name"], r["platform"], r["url"], r["source_kind"], tuple(r["target_modules"]), r["schedule_cron"], r["active"]) for r in rows)


async def test_the_knf_source_is_inserted_once(pool):
    first = await seed_knf(pool)
    second = await seed_knf(pool)

    rows = await pool.fetch("SELECT id::text, platform, source_kind, target_modules, active FROM sources WHERE url = $1", KNF_URL)
    assert first is not None and second is None
    assert [(r["id"], r["platform"], r["source_kind"], list(r["target_modules"]), r["active"]) for r in rows] == [
        (first, "web", "third_party", ["M3"], True)
    ]


async def test_the_cron_is_stored_when_given(pool):
    await seed_knf(pool, cron="0 * * * *")

    assert await pool.fetchval("SELECT schedule_cron FROM sources WHERE url = $1", KNF_URL) == "0 * * * *"


def test_the_cron_comes_from_the_first_argument():
    assert cron_from(["seed", "0 * * * *"]) == "0 * * * *"
    assert cron_from(["seed"]) is None


@pytest.mark.parametrize("bad", ["not a cron", "61 * * * *", "* * * *", ""])
def test_an_invalid_cron_stops_the_seed_before_it_connects(bad):
    with pytest.raises(SystemExit, match="invalid cron"):
        cron_from(["seed", bad])


async def test_a_first_run_inserts_one_active_row_per_entry(pool):
    report = await seed_sources(pool, ENTRIES)

    assert report == (len(ENTRIES), 0)
    expected = sorted((e.name, e.platform, e.url, e.source_kind, e.target_modules, e.schedule_cron, True) for e in ENTRIES)
    assert stored(await pool.fetch("SELECT * FROM sources")) == expected


async def test_a_second_run_adds_nothing_and_reports_every_entry_present(pool):
    await seed_sources(pool, ENTRIES)

    report = await seed_sources(pool, ENTRIES)

    assert report == (0, len(ENTRIES))
    assert await pool.fetchval("SELECT count(*) FROM sources") == len(ENTRIES)


async def test_a_row_edited_in_the_dashboard_keeps_its_values(pool):
    await seed_sources(pool, ENTRIES)
    first = ENTRIES[0]
    await pool.execute("UPDATE sources SET active = false, schedule_cron = '5 5 * * *', name = 'renamed' WHERE url = $1", first.url)

    report = await seed_sources(pool, ENTRIES)

    row = await pool.fetchrow("SELECT name, active, schedule_cron FROM sources WHERE url = $1", first.url)
    assert (row["name"], row["active"], row["schedule_cron"]) == ("renamed", False, "5 5 * * *")
    assert report == (0, len(ENTRIES))


async def test_a_url_already_registered_under_another_name_is_left_alone(pool):
    await seed_knf(pool)
    knf_as_entry = SeedEntry("Same page, seed name", "web", KNF_URL, "third_party", ("M3",), None)

    report = await seed_sources(pool, [knf_as_entry])

    assert report == (0, 1)
    assert await pool.fetchval("SELECT count(*) FROM sources WHERE url = $1", KNF_URL) == 1


async def test_concurrent_runs_leave_one_row_per_url(pool):
    reports = await asyncio.gather(*(seed_sources(pool, ENTRIES) for _ in range(4)))

    assert await pool.fetchval("SELECT count(*) FROM sources") == len(ENTRIES)
    assert sum(inserted for inserted, _ in reports) == len(ENTRIES)


async def test_seed_all_registers_knf_and_the_seed_files_and_reports_both(pool, tmp_path):
    (tmp_path / "one.toml").write_text(
        '[[source]]\nname = "One"\nurl = "https://one.example/a"\nsource_kind = "unknown"\ntarget_modules = ["M3"]\n'
    )

    entries = load_seed_dir(tmp_path)
    first = await seed_all(pool, entries)
    second = await seed_all(pool, entries)

    assert first.splitlines()[1] == "sources: inserted 1, already present 0"
    assert first.splitlines()[0].startswith("inserted ")
    assert second.splitlines() == ["already registered", "sources: inserted 0, already present 1"]
    assert await pool.fetchval("SELECT count(*) FROM sources") == 2


async def test_main_writes_nothing_when_a_seed_file_is_invalid(pool, tmp_path, monkeypatch):
    (tmp_path / "bad.toml").write_text(
        '[[source]]\nname = "Bad"\nurl = "http://bad.example/a"\nsource_kind = "unknown"\ntarget_modules = ["M3"]\n'
    )
    schema = await pool.fetchval("SELECT current_schema()")
    dsn = os.environ["IW_TEST_PG_DSN"]
    monkeypatch.setenv("DATABASE_URL", f"{dsn}{'&' if '?' in dsn else '?'}search_path={schema}")
    monkeypatch.setattr("iw_scraper.seed.SEEDS_DIR", tmp_path)
    monkeypatch.setattr("sys.argv", ["seed"])

    with pytest.raises(SystemExit, match="bad.toml"):
        await main()

    assert await pool.fetchval("SELECT count(*) FROM sources") == 0


async def test_every_seeded_host_is_allowed_with_no_extra_hosts_and_a_foreign_hop_is_refused(pool):
    await seed_sources(pool, WEB_ENTRIES)
    guard = await allowed_urls(PgSourceStore(pool), [], (80, 443))()  # FETCH_EXTRA_HOSTS empty

    for entry in WEB_ENTRIES:
        guard.check(entry.url)
        guard.check(urlsplit(entry.url)._replace(path="/elsewhere", query="").geturl())  # a redirect within the host
    with pytest.raises(FetchFailure) as refused:
        guard.check("https://not-seeded.example/landing")  # a redirect to a host no row names
    assert refused.value.reason is Reason.BLOCKED_TARGET


async def test_main_registers_the_seed_files_and_prints_the_report(pool, monkeypatch, capsys):
    schema = await pool.fetchval("SELECT current_schema()")
    dsn = os.environ["IW_TEST_PG_DSN"]
    monkeypatch.setenv("DATABASE_URL", f"{dsn}{'&' if '?' in dsn else '?'}search_path={schema}")  # asyncpg: unknown parameters are server settings
    monkeypatch.setattr("sys.argv", ["seed", "5 4 * * *"])

    await main()

    assert f"sources: inserted {len(ENTRIES)}, already present 0" in capsys.readouterr().out
    assert await pool.fetchval("SELECT count(*) FROM sources WHERE url <> $1", KNF_URL) == len(ENTRIES)
    assert await pool.fetchval("SELECT schedule_cron FROM sources WHERE url = $1", KNF_URL) == "5 4 * * *"


@pytest.mark.parametrize("write", [lambda pool: seed_knf(pool), lambda pool: seed_sources(pool, ENTRIES)], ids=["knf", "sources"])
async def test_a_writer_waits_while_another_seed_run_holds_the_lock(pool, write):
    async with pool.acquire() as holder, holder.transaction():
        await holder.execute("SELECT pg_advisory_xact_lock($1)", _LOCK_KEY)
        pending = asyncio.ensure_future(write(pool))

        done, _ = await asyncio.wait({pending}, timeout=0.5)

        assert not done
    await asyncio.wait_for(pending, timeout=5)


async def test_concurrent_full_runs_leave_one_row_per_url_including_knf(pool, tmp_path):
    (tmp_path / "one.toml").write_text(
        '[[source]]\nname = "One"\nurl = "https://one.example/a"\nsource_kind = "unknown"\ntarget_modules = ["M3"]\n'
    )
    entries = load_seed_dir(tmp_path)
    await asyncio.gather(*(seed_all(pool, entries) for _ in range(6)))

    assert await pool.fetchval("SELECT count(*) FROM sources WHERE url = $1", KNF_URL) == 1


async def test_a_database_error_after_connecting_exits_with_a_fixed_message(pool, monkeypatch):
    # the public schema of the test database has no `sources` table, so the first query fails after the connection worked
    monkeypatch.setenv("DATABASE_URL", os.environ["IW_TEST_PG_DSN"])
    monkeypatch.setattr("sys.argv", ["seed"])  # not pytest's own arguments: the first one is read as the cron

    with pytest.raises(SystemExit) as failed:
        await main()

    assert failed.value.code == "the database failed while seeding (check DATABASE_URL and that the schema is migrated)"


async def test_a_bug_after_connecting_is_not_reported_as_a_database_failure(pool, monkeypatch):
    async def broken(*args, **kwargs):
        raise ValueError("a bug of ours")

    monkeypatch.setattr("iw_scraper.seed.seed_all", broken)
    monkeypatch.setenv("DATABASE_URL", os.environ["IW_TEST_PG_DSN"])
    monkeypatch.setattr("sys.argv", ["seed"])

    with pytest.raises(ValueError, match="a bug of ours"):
        await main()


async def test_a_malformed_database_url_exits_without_echoing_it(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://seeduser:s3cr3t-pw@localhost:notaport/seeddb")  # asyncpg raises a bare ValueError

    with pytest.raises(SystemExit) as failed:
        await main()

    assert failed.value.code == "cannot connect to the database (check DATABASE_URL)"


async def test_a_missing_database_url_exits_with_a_message(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(SystemExit) as failed:
        await main()

    assert failed.value.code == "DATABASE_URL is not set"


UNREACHABLE_DSN = "postgresql://seeduser:s3cr3t-pw@127.0.0.1:1/seeddb"  # no database listens there


async def test_main_exits_with_the_message_of_an_invalid_seed_file_without_a_database(monkeypatch):
    def refuse(directory):
        raise SeedError("sources.toml entry 1 ('X'): boom")

    monkeypatch.setattr("iw_scraper.seed.load_seed_dir", refuse)
    monkeypatch.setenv("DATABASE_URL", UNREACHABLE_DSN)

    with pytest.raises(SystemExit) as refused:
        await main()

    assert refused.value.code == "sources.toml entry 1 ('X'): boom"


@pytest.mark.parametrize("schema", [None, "{", "{}", '{"properties": []}'], ids=["missing", "not-json", "no-properties", "wrong-shape"])
async def test_main_names_an_unreadable_contract_schema_without_a_database(monkeypatch, tmp_path, schema):
    if schema is not None:
        (tmp_path / "schemas").mkdir()
        (tmp_path / "schemas" / "source.schema.json").write_text(schema)
    monkeypatch.setenv("CONTRACTS_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", UNREACHABLE_DSN)

    with pytest.raises(SystemExit) as refused:
        await main()

    assert "source contract schema" in str(refused.value.code)
    assert str(tmp_path) in str(refused.value.code)


def test_the_contract_schema_is_read_once_for_all_entries(monkeypatch):
    reads = []
    original = seed_module._contract_values
    monkeypatch.setattr("iw_scraper.seed._contract_values", lambda: reads.append(1) or original())

    load_seed_dir(SEEDS_DIR)

    assert len(reads) == 1


async def test_an_unreachable_database_exits_without_the_connection_string(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://seeduser:s3cr3t-pw@127.0.0.1:1/seeddb")

    with pytest.raises(SystemExit) as failed:
        await main()

    message = str(failed.value.code)
    assert failed.value.code not in (0, None)
    assert "s3cr3t-pw" not in message and "seeduser" not in message and "seeddb" not in message
