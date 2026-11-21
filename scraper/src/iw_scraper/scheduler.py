"""Cron scheduling: every due (source, minute) gets one job with a unique id, however many schedulers run."""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

from arq.connections import ArqRedis
from croniter import croniter

from iw_scraper.sources import SourceStore, domain_of
from iw_scraper.types import JobError, Reason

MINUTE = timedelta(minutes=1)
MAX_CATCH_UP_SLOTS = 5  # a late tick still covers the minutes it missed, but never replays hours

logger = logging.getLogger(__name__)


class Scheduler:
    def __init__(
        self,
        redis: ArqRedis,
        store: SourceStore,
        record_error,
        *,
        sweep: Callable[[], Awaitable[None]] | None = None,
        tick_interval: float = 60.0,
        sweep_interval: float = 3600.0,
    ) -> None:
        self._redis = redis
        self._store = store
        self._record_error = record_error
        self._sweep = sweep
        self._tick_interval = tick_interval
        self._sweep_interval = sweep_interval
        self._last_slot: datetime | None = None

    async def tick(self, now: datetime) -> int:
        """Enqueue the jobs due since the last tick; returns how many this scheduler actually enqueued."""
        current = now.astimezone(UTC).replace(second=0, microsecond=0)
        if self._last_slot is None:
            self._last_slot = current - MINUTE  # the first tick covers its own minute; a failure keeps it owed
        slots = self._slots_since_last_tick(current)
        enqueued = 0
        for source in await self._store.schedulable():
            if not source.collectable or source.schedule_cron is None:
                continue
            if not domain_of(source):
                logger.warning("source %s has a URL without a host and is not scheduled", source.id)
                continue
            if not croniter.is_valid(source.schedule_cron):
                await self._note_invalid_cron(source.id, source.schedule_cron)
                continue
            await self._redis.delete(self._invalid_key(source.id))
            for slot in slots:
                if croniter.match(source.schedule_cron, slot):
                    job = await self._redis.enqueue_job(
                        "execute_job",
                        source.id,
                        domain_of(source),
                        False,
                        _job_id=f"sched-{source.id}-{slot:%Y%m%dT%H%MZ}",
                    )
                    enqueued += job is not None  # None: another scheduler enqueued this slot already
        self._last_slot = max(current, self._last_slot)  # only after every enqueue went through
        return enqueued

    def _slots_since_last_tick(self, current: datetime) -> list[datetime]:
        first = self._last_slot + MINUTE
        slots = []
        while first <= current:
            slots.append(first)
            first += MINUTE
        return slots[-MAX_CATCH_UP_SLOTS:]

    @staticmethod
    def _invalid_key(source_id: str) -> str:
        return f"iw:cron-invalid:{source_id}"

    async def _note_invalid_cron(self, source_id: str, cron: str) -> None:
        """Record one job error per invalid value, however many ticks and schedulers see it."""
        previous = await self._redis.set(self._invalid_key(source_id), cron, get=True)
        if previous not in (cron, cron.encode()):
            await self._record_error(JobError(Reason.INVALID_REQUEST, "schedule_cron is not a valid cron expression", source_id))

    async def run(self) -> None:
        """Tick and sweep until cancelled; a failed tick or sweep is logged and tried again."""
        next_sweep = time.monotonic() + self._sweep_interval
        while True:
            try:
                await self.tick(datetime.now(UTC))
            except Exception:
                logger.exception("scheduler tick failed")
            if self._sweep and time.monotonic() >= next_sweep:
                next_sweep = time.monotonic() + self._sweep_interval
                try:
                    await self._sweep()
                except Exception:
                    logger.exception("republish sweep failed")
            await asyncio.sleep(self._tick_interval)
