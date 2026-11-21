"""Opt-in live check of the seeded pages (`pytest -m scraper_live tests/test_seed_live.py`).

Deselected by default and outside CI: it makes real requests to the seeded hosts and needs outbound HTTPS, no
other service and no proxy. Per entry it asks `robots.txt` once, then fetches the page through the production
stages (the same guards, identity, TLS client and redirect handling as `run_source`), spaced like a run by the
request interval. An entry fails when robots refuses it, the fetch is blocked or fails, it redirects to another
URL, the status is not 200, or the page has no text. Nothing is stored.
"""

import uuid

import pytest

from iw_scraper.collect import Stages
from iw_scraper.fetch import FetchDeferred, FetchFailure
from iw_scraper.proxy import ProxyRotator
from iw_scraper.ratelimit import LocalLimiter, domain_key
from iw_scraper.seed import SEEDS_DIR, SeedEntry, load_seed_dir
from iw_scraper.targets import AddressGuard, UrlGuard, target_guard
from iw_scraper.types import Source

pytestmark = pytest.mark.scraper_live

REQUEST_INTERVAL_SECONDS = 5.0  # the scraper's default gap between two request starts on one domain
TIMEOUT_SECONDS = 20.0
MAX_BYTES = 5 * 1024 * 1024
ENTRIES = [entry for entry in load_seed_dir(SEEDS_DIR) if entry.platform == "web"]  # the web fetch path is all this check drives


async def check_entry(entry: SeedEntry, *, addresses, limiter, stages: Stages = Stages()) -> None:
    """Raise AssertionError naming the entry (and both URLs of a redirect) unless its page is final and fetchable."""
    source = Source(
        id=str(uuid.uuid4()), name=entry.name, platform=entry.platform, url=entry.url, source_kind=entry.source_kind,
        target_modules=entry.target_modules, active=True, schedule_cron=entry.schedule_cron,
    )
    guard = target_guard(UrlGuard.for_sources([source]), addresses, entry.url)
    proxy = ProxyRotator([], "per_request", 90.0).start_run()
    identity = stages.draw_identity()
    session = stages.open_session(identity)
    domain = domain_key(entry.url)
    try:
        await limiter.wait_turn(domain)
        verdict = await stages.check_robots(entry.url, identity, proxy, guard=guard, timeout=TIMEOUT_SECONDS, session=session)
        assert verdict.allowed, f"{entry.name}: robots.txt refuses {entry.url} ({verdict.detail})"
        await limiter.wait_turn(domain)
        result = await stages.fetch(
            entry.url, identity, proxy, guard=guard, timeout=TIMEOUT_SECONDS, max_bytes=MAX_BYTES, session=session
        )
        assert result.url == entry.url, f"{entry.name}: {entry.url} redirects to {result.url}"
        assert result.status == 200, f"{entry.name}: {entry.url} answers {result.status}"
        page = stages.parse(result.body, result.content_type, result.url)
        assert page.text.strip(), f"{entry.name}: {entry.url} has no text"
    except FetchFailure as failure:
        raise AssertionError(f"{entry.name}: {entry.url}: {failure.reason.value}: {failure.detail}") from None
    except FetchDeferred:
        raise AssertionError(f"{entry.name}: {entry.url}: the fetch was deferred") from None
    finally:
        await stages.close_session(session)


@pytest.fixture(scope="module")
def limiter() -> LocalLimiter:
    return LocalLimiter(REQUEST_INTERVAL_SECONDS)  # one process, so the local limiter is the whole story


@pytest.mark.parametrize("entry", ENTRIES, ids=lambda entry: entry.name)
async def test_a_seeded_page_is_final_and_fetchable(entry, limiter):
    await check_entry(entry, addresses=AddressGuard(), limiter=limiter)
