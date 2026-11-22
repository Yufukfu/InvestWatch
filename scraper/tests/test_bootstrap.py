"""First-run bootstrap: one scan request per active, scheduled, never-run source, once."""

import os
import uuid
from datetime import UTC, datetime

import pytest

from iw_scraper.bootstrap import bootstrap_enabled, enqueue_never_run, run

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
