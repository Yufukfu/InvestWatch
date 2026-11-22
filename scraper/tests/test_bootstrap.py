"""First-run bootstrap: one scan request per active, scheduled, never-run source, once."""

import json
import os
import uuid
from datetime import UTC, datetime

import pytest

from iw_scraper.bootstrap import bootstrap_enabled, collect_status, enqueue_never_run, exit_code, main, run, status_main

STREAM = "iw:scan-requests"


async def add_source(pool, *, cron="0 6 * * *", active=True, last_run_at=None, platform="web", url=None) -> str:
    source_id = str(uuid.uuid4())
    await pool.execute(
        "INSERT INTO sources (id, name, platform, url, source_kind, target_modules, schedule_cron, active, last_run_at, last_run_status)"
        " VALUES ($1, 'n', $2, $3, 'unknown', ARRAY['M1'], $4, $5, $6, $7)",
        uuid.UUID(source_id), platform, url or f"https://example.test/{source_id}", cron, active, last_run_at,
        "ok" if last_run_at else None,
    )
    return source_id


async def requested_ids(redis) -> list[str]:
    return sorted(fields[b"source_id"].decode() for _, fields in await redis.xrange(STREAM))


async def test_an_active_scheduled_never_run_source_gets_one_request(pool, redis):
    source_id = await add_source(pool)

    enqueued = await enqueue_never_run(pool, redis)

    assert enqueued == [source_id]
    assert await requested_ids(redis) == [source_id]


async def test_the_request_has_the_contract_shape(pool, redis):
    await add_source(pool)

    await enqueue_never_run(pool, redis)

    [(_, fields)] = await redis.xrange(STREAM)
    assert set(fields) == {b"source_id", b"requested_at"}
    datetime.strptime(fields[b"requested_at"].decode(), "%Y-%m-%dT%H:%M:%SZ")


async def test_inactive_manual_and_already_run_sources_get_none(pool, redis):
    await add_source(pool, active=False)
    await add_source(pool, cron=None)
    await add_source(pool, last_run_at=datetime.now(UTC))

    assert await enqueue_never_run(pool, redis) == []
    assert await redis.xlen(STREAM) == 0


async def test_a_source_without_a_social_collector_is_not_collectable(pool, redis):
    await add_source(pool, platform="facebook")

    assert await enqueue_never_run(pool, redis) == []


async def test_a_second_run_enqueues_nothing_even_before_the_worker_consumed_the_first(pool, redis):
    source_id = await add_source(pool)

    await enqueue_never_run(pool, redis)
    again = await enqueue_never_run(pool, redis)

    assert again == []
    assert await requested_ids(redis) == [source_id]


class FailingXadd:
    """The real Redis, except that `xadd` fails."""

    def __init__(self, redis) -> None:
        self._redis = redis

    def __getattr__(self, name):
        return getattr(self._redis, name)

    async def xadd(self, *args, **kwargs):
        raise ConnectionError("down")


async def test_a_failed_xadd_leaves_the_source_for_the_next_run(pool, redis):
    source_id = await add_source(pool)

    with pytest.raises(ConnectionError):
        await enqueue_never_run(pool, FailingXadd(redis))

    assert await enqueue_never_run(pool, redis) == [source_id]


@pytest.mark.parametrize(("value", "expected"), [(None, True), ("", True), ("true", True), ("false", False)])
def test_bootstrap_scan_is_a_boolean_with_default_true(value, expected):
    environ = {} if value is None else {"BOOTSTRAP_SCAN": value}

    assert bootstrap_enabled(environ) is expected


@pytest.mark.parametrize("value", ["yes", "1", "False", "TRUE "])
def test_bootstrap_scan_refuses_anything_else_naming_the_variable(value):
    with pytest.raises(SystemExit, match="BOOTSTRAP_SCAN"):
        bootstrap_enabled({"BOOTSTRAP_SCAN": value})


async def test_disabled_bootstrap_touches_neither_database_nor_redis():
    await run({"BOOTSTRAP_SCAN": "false"})  # no DATABASE_URL or REDIS_URL: reading either would exit


async def test_an_invalid_flag_exits_before_any_connection():
    with pytest.raises(SystemExit, match="BOOTSTRAP_SCAN"):
        await run({"BOOTSTRAP_SCAN": "maybe", "DATABASE_URL": "postgresql://x@127.0.0.1:1/x", "REDIS_URL": "redis://127.0.0.1:1/0"})


async def test_unreachable_redis_exits_with_the_reason_and_queues_nothing(pool, redis):
    await add_source(pool)
    schema = await pool.fetchval("SHOW search_path")
    environ = {"DATABASE_URL": f"{os.environ['IW_TEST_PG_DSN']}?search_path={schema}", "REDIS_URL": "redis://127.0.0.1:1/0"}

    with pytest.raises(SystemExit, match="Redis"):
        await run(environ)

    assert await redis.xlen(STREAM) == 0


async def test_unreachable_database_exits_with_the_reason():
    with pytest.raises(SystemExit, match="database"):
        await run({"DATABASE_URL": "postgresql://u:secret@127.0.0.1:1/x", "REDIS_URL": os.environ["REDIS_URL"]})


# --- status ---


async def add_document(pool, source_id: str) -> str:
    document_id = uuid.uuid4()
    await pool.execute(
        "INSERT INTO documents (id, source_id, platform, source_kind, url, fetched_at, text, content_hash)"
        " VALUES ($1, $2, 'web', 'unknown', $3, now(), 'x', $4)",
        document_id, uuid.UUID(source_id), f"https://example.test/{document_id}", uuid.uuid4().hex * 2,
    )
    return str(document_id)


async def add_finding(pool, document_id: str, module: str) -> None:
    await pool.execute("INSERT INTO findings (id, document_id, module) VALUES ($1, $2, $3)", uuid.uuid4(), uuid.UUID(document_id), module)


async def add_calibration(pool, module: str) -> None:
    await pool.execute("INSERT INTO calibration_points (run_id, module, threshold) VALUES ($1, $2, 0.5)", uuid.uuid4(), module)


async def add_job_error(pool, source_id: str, reason: str) -> None:
    await pool.execute("INSERT INTO job_errors (id, source_id, reason) VALUES ($1, $2, $3)", uuid.uuid4(), uuid.UUID(source_id), reason)


async def finished_source(pool, *, failed=False, **kwargs) -> str:
    source_id = await add_source(pool, last_run_at=datetime.now(UTC), **kwargs)
    if failed:
        await pool.execute("UPDATE sources SET last_run_status = 'failed' WHERE id = $1", uuid.UUID(source_id))
    return source_id


async def complete_run(pool) -> str:
    source_id = await finished_source(pool)
    document_id = await add_document(pool, source_id)
    for module in ("M1", "M2", "M3"):
        await add_finding(pool, document_id=await add_document(pool, source_id) if module != "M1" else document_id, module=module)
        await add_calibration(pool, module)
    return source_id


def states(report) -> dict[str, str]:
    return {entry["id"]: entry["state"] for entry in report["sources"]}


async def test_a_complete_run_is_ready(pool):
    source_id = await complete_run(pool)

    report = await collect_status(pool)

    assert report["ready"] is True and exit_code(report) == 0
    assert states(report) == {source_id: "scanned"}
    assert report["documents"] == 3
    assert report["findings"] == {"M1": 1, "M2": 1, "M3": 1}
    assert report["calibration_points"] == {"M1": 1, "M2": 1, "M3": 1}
    assert report["missing_modules"] == []


async def test_a_module_without_a_finding_is_not_ready_and_is_named(pool):
    source_id = await finished_source(pool)
    document_id = await add_document(pool, source_id)
    await add_finding(pool, document_id, "M1")

    report = await collect_status(pool)

    assert exit_code(report) == 1
    assert report["missing_modules"] == ["M2", "M3"]


async def test_a_pending_source_is_not_ready_even_when_every_module_has_a_finding(pool):
    await complete_run(pool)
    pending = await add_source(pool)  # cron, never ran

    report = await collect_status(pool)

    assert states(report)[pending] == "pending"
    assert exit_code(report) == 1


async def test_a_running_rescan_counts_as_pending(pool):
    source_id = await add_source(pool, last_run_at=datetime.now(UTC))
    await pool.execute("UPDATE sources SET last_run_status = 'running' WHERE id = $1", uuid.UUID(source_id))

    assert states(await collect_status(pool))[source_id] == "pending"


async def test_a_failed_source_shows_its_latest_reason_and_does_not_block_readiness(pool):
    await complete_run(pool)
    failed = await finished_source(pool, failed=True)
    await add_job_error(pool, failed, "timeout")
    await pool.execute("INSERT INTO job_errors (id, source_id, reason, occurred_at) VALUES ($1, $2, 'blocked', now() + interval '1 minute')", uuid.uuid4(), uuid.UUID(failed))

    report = await collect_status(pool)

    [entry] = [e for e in report["sources"] if e["id"] == failed]
    assert (entry["state"], entry["reason"]) == ("failed", "blocked")
    assert exit_code(report) == 0


async def test_a_never_run_source_without_a_cron_is_manual_and_does_not_block_readiness(pool):
    await complete_run(pool)
    manual = await add_source(pool, cron=None)

    report = await collect_status(pool)

    assert states(report)[manual] == "manual"
    assert exit_code(report) == 0


async def test_inactive_sources_are_not_listed(pool):
    inactive = await add_source(pool, active=False)

    assert inactive not in states(await collect_status(pool))


async def test_status_changes_no_data(pool):
    await complete_run(pool)
    await add_source(pool)
    tables = ("sources", "documents", "findings", "calibration_points", "job_errors")
    before = [await pool.fetchval(f"SELECT count(*) FROM {t}") for t in tables]
    changed = await pool.fetchval("SELECT md5(string_agg(last_run_status || coalesce(last_run_at::text, ''), ',' ORDER BY id)) FROM sources")

    await collect_status(pool)

    assert [await pool.fetchval(f"SELECT count(*) FROM {t}") for t in tables] == before
    assert await pool.fetchval("SELECT md5(string_agg(last_run_status || coalesce(last_run_at::text, ''), ',' ORDER BY id)) FROM sources") == changed


async def test_status_cli_prints_json_and_exits_with_the_code(pool, capsys):
    await complete_run(pool)
    schema = await pool.fetchval("SHOW search_path")
    environ = {"DATABASE_URL": f"{os.environ['IW_TEST_PG_DSN']}?search_path={schema}"}

    code = await status_main(environ)

    assert code == 0
    assert json.loads(capsys.readouterr().out)["ready"] is True


async def test_status_with_an_unreachable_database_exits_2_and_prints_nothing(capsys):
    code = await status_main({"DATABASE_URL": "postgresql://u:secret@127.0.0.1:1/x"})

    out = capsys.readouterr()
    assert code == 2 and out.out == ""
    assert "database" in out.err and "secret" not in out.err


async def test_a_scanned_source_shows_no_reason_even_with_an_old_job_error(pool):
    source_id = await finished_source(pool)
    await add_job_error(pool, source_id, "timeout")

    [entry] = (await collect_status(pool))["sources"]

    assert (entry["state"], entry["reason"]) == ("scanned", None)


def test_the_command_line_routes_status_and_refuses_other_arguments(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:secret@127.0.0.1:1/x")

    with pytest.raises(SystemExit) as status:
        main(["bootstrap", "status"])
    with pytest.raises(SystemExit, match="usage"):
        main(["bootstrap", "enqueue"])

    assert status.value.code == 2
