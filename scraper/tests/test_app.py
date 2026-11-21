"""`allowed_urls`: the redirect allow-list follows the `sources` table without a query per run."""

import asyncio
import logging

import pytest

from conftest import make_source
from iw_scraper.app import _run_together, allowed_urls, main
from iw_scraper.types import Reason
from iw_scraper.fetch import FetchFailure


class Store:
    def __init__(self, urls):
        self.urls, self.queries = list(urls), 0

    async def collectable(self):
        self.queries += 1
        return [make_source(f"id-{n}", url=url) for n, url in enumerate(self.urls)]


class Clock:
    now = 0.0

    def __call__(self):
        return self.now


def refuses(guard, url):
    with pytest.raises(FetchFailure) as caught:
        guard.check(url)
    assert caught.value.reason is Reason.BLOCKED_TARGET


async def test_hosts_of_collectable_sources_and_extras_are_allowed():
    urls = allowed_urls(Store(["https://alfa.example.com/a"]), ["extra.example.org"], (443,), clock=Clock())

    guard = await urls()

    guard.check("https://alfa.example.com/other")
    guard.check("https://extra.example.org/x")
    refuses(guard, "https://other.example.net/")


async def test_the_list_is_cached_for_the_ttl_then_reread():
    store, clock = Store(["https://alfa.example.com/"]), Clock()
    urls = allowed_urls(store, [], (443,), ttl=60.0, clock=clock)

    await urls()
    store.urls.append("https://beta.example.com/")
    clock.now = 59.0
    stale = await urls()
    clock.now = 60.0
    fresh = await urls()

    refuses(stale, "https://beta.example.com/")
    fresh.check("https://beta.example.com/")
    assert store.queries == 2


async def test_a_part_that_fails_stops_the_others_and_the_error_is_raised_after_they_drained():
    stop, drained = asyncio.Event(), []

    async def failing():
        raise RuntimeError("boom")

    async def long_running():
        await stop.wait()
        await asyncio.sleep(0.05)  # draining takes a moment
        drained.append(True)

    with pytest.raises(RuntimeError, match="boom"):
        async with asyncio.timeout(3):  # a sibling that is never stopped must fail the test, not hang it
            await _run_together(stop, failing(), long_running())

    assert drained == [True]


async def test_parts_that_all_end_cleanly_return_normally():
    stop = asyncio.Event()

    async def finishes():
        return None

    await _run_together(stop, finishes(), finishes())


def test_a_process_that_cannot_start_exits_non_zero(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    root_handlers = list(logging.getLogger().handlers)

    with pytest.raises(SystemExit) as caught:
        main("worker")

    assert caught.value.code == 1
    logging.getLogger().handlers[:] = root_handlers
