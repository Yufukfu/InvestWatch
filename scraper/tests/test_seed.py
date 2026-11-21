import asyncio
import os

import pytest

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

    first = await seed_all(pool, directory=tmp_path)
    second = await seed_all(pool, directory=tmp_path)

    assert first.splitlines()[1] == "sources: inserted 1, already present 0"
    assert first.splitlines()[0].startswith("inserted ")
    assert second.splitlines() == ["already registered", "sources: inserted 0, already present 1"]
    assert await pool.fetchval("SELECT count(*) FROM sources") == 2


async def test_seed_all_writes_nothing_when_a_seed_file_is_invalid(pool, tmp_path):
    (tmp_path / "bad.toml").write_text(
        '[[source]]\nname = "Bad"\nurl = "http://bad.example/a"\nsource_kind = "unknown"\ntarget_modules = ["M3"]\n'
    )

    with pytest.raises(SeedError, match="bad.toml"):
        await seed_all(pool, directory=tmp_path)

    assert await pool.fetchval("SELECT count(*) FROM sources") == 0


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
    await asyncio.gather(*(seed_all(pool, directory=tmp_path) for _ in range(6)))

    assert await pool.fetchval("SELECT count(*) FROM sources WHERE url = $1", KNF_URL) == 1


async def test_a_database_error_after_connecting_exits_with_a_fixed_message(pool, monkeypatch):
    # the public schema of the test database has no `sources` table, so the first query fails after the connection worked
    monkeypatch.setenv("DATABASE_URL", os.environ["IW_TEST_PG_DSN"])

    with pytest.raises(SystemExit) as failed:
        await main()

    assert failed.value.code == "the database failed while seeding (check DATABASE_URL and that the schema is migrated)"


async def test_a_missing_database_url_exits_with_a_message(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(SystemExit) as failed:
        await main()

    assert failed.value.code == "DATABASE_URL is not set"


async def test_main_exits_with_the_message_of_an_invalid_seed_file(pool, monkeypatch):
    def refuse(directory):
        raise SeedError("sources.toml entry 1 ('X'): boom")

    monkeypatch.setattr("iw_scraper.seed.load_seed_dir", refuse)
    monkeypatch.setenv("DATABASE_URL", os.environ["IW_TEST_PG_DSN"])

    with pytest.raises(SystemExit) as refused:
        await main()

    assert refused.value.code == "sources.toml entry 1 ('X'): boom"


async def test_an_unreachable_database_exits_without_the_connection_string(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://seeduser:s3cr3t-pw@127.0.0.1:1/seeddb")

    with pytest.raises(SystemExit) as failed:
        await main()

    message = str(failed.value.code)
    assert failed.value.code not in (0, None)
    assert "s3cr3t-pw" not in message and "seeduser" not in message and "seeddb" not in message
