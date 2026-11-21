"""The process side of the queue: arq worker and scan-request consumer, supervised and stoppable.

The caller owns signal handling and sets `stop` (SIGTERM/SIGINT in production): the worker then takes
no new jobs, lets running ones finish for `shutdown_deadline` seconds, and requeues what is left.
"""

import asyncio
import logging
import signal
from dataclasses import dataclass

from arq.connections import RedisSettings
from arq.worker import Worker

from iw_scraper.jobs import QueueSettings, job_function
from iw_scraper.supervise import CONNECTION_ERRORS, supervise

logger = logging.getLogger(__name__)
MAIN_TASK_POLL = 0.01
CLOSE_TIMEOUT = 10.0


@dataclass(frozen=True)
class RunnerSettings:
    redis_url: str
    max_jobs: int = 10
    shutdown_deadline: float = 30.0
    reconnect_base: float = 1.0
    reconnect_cap: float = 30.0
    poll_delay: float = 0.5
    consumer_block: float = 1.0


async def run_worker(
    ctx: dict,
    queue: QueueSettings,
    runner: RunnerSettings,
    *,
    stop: asyncio.Event,
    retry_on: tuple[type[BaseException], ...] = CONNECTION_ERRORS,
) -> None:
    """Run the arq worker until `stop`, rebuilding it with backoff whenever a dependency goes away."""

    async def one_life() -> None:
        worker = Worker(
            functions=[job_function(queue)],
            redis_settings=RedisSettings.from_dsn(runner.redis_url),
            ctx={**ctx, "settings": queue},
            max_jobs=runner.max_jobs,
            poll_delay=runner.poll_delay,
            job_completion_wait=runner.shutdown_deadline,
            retry_jobs=True,  # a job cancelled at the deadline goes back to the queue
            handle_signals=False,
        )
        drain = asyncio.create_task(_drain_when_stopped(worker, stop))
        try:
            await worker.async_run()
        except asyncio.CancelledError:
            if asyncio.current_task().cancelling():
                raise
            # arq cancels its own main task once a graceful stop has finished
        finally:
            drain.cancel()
            await _close(worker)
        if not stop.is_set():
            raise OSError("the worker stopped without being asked to")  # restart it, with backoff

    await supervise(
        one_life, name="worker", stop=stop, base=runner.reconnect_base, cap=runner.reconnect_cap, retry_on=retry_on
    )


async def run_consumer(
    consumer,
    runner: RunnerSettings,
    *,
    stop: asyncio.Event,
    retry_on: tuple[type[BaseException], ...] = CONNECTION_ERRORS,
) -> None:
    """Read scan requests until `stop`, reconnecting with backoff."""

    async def loop() -> None:
        await consumer.setup()
        while not stop.is_set():
            await consumer.poll(block=runner.consumer_block)

    await supervise(
        loop,
        name="scan-request consumer",
        stop=stop,
        base=runner.reconnect_base,
        cap=runner.reconnect_cap,
        retry_on=retry_on,
    )


async def _drain_when_stopped(worker: Worker, stop: asyncio.Event) -> None:
    await stop.wait()
    while worker.main_task is None:  # stop was set before the worker's loop existed
        await asyncio.sleep(MAIN_TASK_POLL)
    worker.handle_sig_wait_for_completion(signal.SIGTERM)


async def _close(worker: Worker) -> None:
    """Let cancelled jobs finish handing themselves back, then close; bounded, Redis may be gone."""
    try:
        async with asyncio.timeout(CLOSE_TIMEOUT):
            # without this, close() (which cancels every task again when signals are not handled by arq)
            # could interrupt a job that is requeueing itself
            await asyncio.gather(*worker.tasks.values(), return_exceptions=True)
            await worker.close()
    except (*CONNECTION_ERRORS, TimeoutError):
        logger.warning("worker could not close cleanly, its dependency is unreachable", exc_info=True)
