import asyncio
import json
import os
from dataclasses import dataclass, field
from datetime import datetime

import jsonschema
import pytest
import redis.asyncio as aioredis
from arq.connections import RedisSettings, create_pool
from arq.worker import Worker

from iw_scraper.config import contracts_dir
from iw_scraper.jobs import QueueSettings, job_function
from iw_scraper.types import JobError, Source


@pytest.fixture
async def redis():
    """A real Redis (REDIS_URL, see scraper/compose.test.yaml), emptied around each test."""
    pool = await create_pool(RedisSettings.from_dsn(os.environ["REDIS_URL"]))
    await pool.flushdb()
    yield pool
    await pool.flushdb()
    await pool.aclose()


def fast_settings(**overrides) -> QueueSettings:
    base = dict(
        max_tries=3,
        backoff_base=0.05,
        backoff_cap=0.5,
        attempt_timeout=5.0,
        domain_concurrency=2,
        lease_ttl=1.0,
        requeue_delay=0.05,
        failure_threshold=5,
        domain_cooldown=0.5,
    )
    return QueueSettings(**{**base, **overrides})


@dataclass
class Recorder:
    """Stands in for the collector stages and the job-error sink."""

    errors: list[JobError] = field(default_factory=list)

    async def record_error(self, error: JobError) -> None:
        self.errors.append(error)


def make_source(source_id, *, active=True, platform="web", cron=None, url="https://example.test/page") -> Source:
    return Source(
        id=source_id, name="s", platform=platform, url=url, source_kind="firm_own",
        target_modules=("M1",), active=active, schedule_cron=cron,
    )


class FakeSourceStore:
    """In-memory `sources` table. `permissive` makes any unknown id an active web source."""

    def __init__(self) -> None:
        self.sources: dict[str, Source] = {}
        self.status: dict[str, dict] = {}
        self.permissive = True

    async def get(self, source_id):
        if source_id in self.sources:
            return self.sources[source_id]
        return make_source(source_id) if self.permissive else None

    async def mark_running(self, source_id) -> None:
        self.status[source_id] = {"last_run_status": "running"}

    async def mark_finished(self, source_id, *, at: datetime, status: str, documents: int) -> None:
        self.status[source_id] = {"last_run_at": at, "last_run_status": status, "documents_count": documents}

    async def schedulable(self):
        return list(self.sources.values())


@pytest.fixture
def store() -> FakeSourceStore:
    return FakeSourceStore()


_EVENT_SCHEMA = json.loads((contracts_dir() / "schemas" / "events.schema.json").read_text())
_EVENT_VALIDATOR = jsonschema.Draft202012Validator({"$ref": "#/$defs/event", "$defs": _EVENT_SCHEMA["$defs"]})


@pytest.fixture
async def events():
    """Everything published on Pub/Sub `iw:events`, each message checked against the contract."""
    client = aioredis.from_url(os.environ["REDIS_URL"])
    pubsub = client.pubsub()
    await pubsub.subscribe("iw:events")
    received: list[dict] = []

    async def pump():
        async for message in pubsub.listen():
            if message["type"] == "message":
                body = json.loads(message["data"])
                _EVENT_VALIDATOR.validate(body)
                received.append(body)

    task = asyncio.create_task(pump())
    await asyncio.sleep(0.1)
    yield received
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    await pubsub.aclose()
    await client.aclose()


@pytest.fixture
async def start_worker(store):
    """Start in-process arq workers (each with its own Redis pool); returns the worker's task."""
    started: list[tuple[Worker, asyncio.Task]] = []

    def start(run_source, recorder: Recorder, settings: QueueSettings, **worker_kwargs) -> asyncio.Task:
        worker = Worker(
            functions=[job_function(settings)],
            redis_settings=RedisSettings.from_dsn(os.environ["REDIS_URL"]),
            ctx={"settings": settings, "run_source": run_source, "record_error": recorder.record_error, "sources": store},
            poll_delay=0.02,
            max_jobs=worker_kwargs.pop("max_jobs", 10),
            handle_signals=False,
            **worker_kwargs,
        )
        task = asyncio.create_task(worker.async_run())
        started.append((worker, task))
        return task

    yield start
    for worker, task in started:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await worker.close()
