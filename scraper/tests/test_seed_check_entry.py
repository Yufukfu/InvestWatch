"""`check_entry` of the live check, run against fake stages: no network. It is what makes the live check's verdicts trustworthy."""

from dataclasses import replace

import pytest

from iw_scraper.collect import Stages
from iw_scraper.fetch import FetchFailure, FetchResult
from iw_scraper.parsing import ParsedPage
from iw_scraper.robots import RobotsVerdict
from iw_scraper.types import Reason
from test_seed_live import ENTRIES, check_entry

ENTRY = ENTRIES[0]


class Addresses:
    async def check(self, host: str) -> str:
        return "93.184.216.34"


class Limiter:
    async def wait_turn(self, key: str) -> float:
        return 0.0


def fake_stages(calls: list[str], *, allowed=True, final_url=None, status=200, text="some text", failure=None) -> Stages:
    async def robots(*args, **kwargs):
        calls.append("robots")
        return RobotsVerdict(allowed, "Disallow: /")

    async def fetch(*args, **kwargs):
        calls.append("fetch")
        if failure:
            raise failure
        return FetchResult(final_url or ENTRY.url, status, "text/html; charset=utf-8", b"<p>x</p>", {}, None)

    async def close(session):
        calls.append("close")

    return replace(
        Stages(), open_session=lambda identity: object(), close_session=close, check_robots=robots, fetch=fetch,
        parse=lambda body, content_type, url: ParsedPage(None, url, text, ()),
    )


async def run(calls: list[str], **kwargs) -> None:
    await check_entry(ENTRY, addresses=Addresses(), limiter=Limiter(), stages=fake_stages(calls, **kwargs))


async def test_a_stable_page_passes_and_is_requested_once():
    calls: list[str] = []

    await run(calls)

    assert calls == ["robots", "fetch", "close"]


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"final_url": ENTRY.url + "moved/"}, f"{ENTRY.url} redirects to {ENTRY.url}moved/"),
        ({"status": 203}, "answers 203"),
        ({"text": "  "}, "has no text"),
        ({"failure": FetchFailure(Reason.BLOCKED, "HTTP 403")}, "blocked: HTTP 403"),
    ],
    ids=["page moved", "not 200", "no text", "blocked"],
)
async def test_a_bad_page_fails_naming_the_entry_and_the_urls(kwargs, message):
    with pytest.raises(AssertionError) as failed:
        await run([], **kwargs)

    assert ENTRY.name in str(failed.value) and message in str(failed.value)


async def test_a_robots_refusal_fails_and_no_page_is_requested():
    calls: list[str] = []

    with pytest.raises(AssertionError, match="robots.txt refuses"):
        await run(calls, allowed=False)

    assert calls == ["robots", "close"]
