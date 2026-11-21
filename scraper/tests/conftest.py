import asyncio
import os
from dataclasses import dataclass, field

import pytest
from arq.connections import RedisSettings, create_pool
from arq.worker import Worker

from iw_scraper.jobs import QueueSettings, job_function
from iw_scraper.types import JobError


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


@pytest.fixture
async def start_worker():
    """Start in-process arq workers (each with its own Redis pool); returns the worker's task."""
    started: list[tuple[Worker, asyncio.Task]] = []

    def start(run_source, recorder: Recorder, settings: QueueSettings, **worker_kwargs) -> asyncio.Task:
        worker = Worker(
            functions=[job_function(settings)],
            redis_settings=RedisSettings.from_dsn(os.environ["REDIS_URL"]),
            ctx={"settings": settings, "run_source": run_source, "record_error": recorder.record_error},
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
