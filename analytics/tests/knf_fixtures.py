"""Saved KNF snapshots (tests/fixtures/knf, trimmed real pages of 2026-11-21) behind a fake fetcher. No network."""

from __future__ import annotations

import re
from pathlib import Path

from investwatch_analytics.knf.fetch import LISTS, SUMMARY_URL

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "knf"


def read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


#: list key -> fixture per page; a page past the last answers like KNF does: the last page again.
PAGES = {
    "brokerage_houses": ["dm_p1.html", "dm_p2.html"],
    "banks": ["banks.html"],
    "branches": ["branches.html"],
    # The real list has 36 pages; the snapshots keep pages 1, 2 and the last (36), served here as 1-3.
    "no_branch": ["nobranch_p1.html", "nobranch_p2.html", "nobranch_p36.html"],
}


class FakeFetcher:
    def __init__(self, pages: dict[str, list[str]] | None = None, summary: str | None = None,
                 overrides: dict[str, str | Exception] | None = None):
        self.pages = PAGES if pages is None else pages
        self.summary = read("summary.html") if summary is None else summary
        self.overrides = overrides or {}
        self.calls: list[str] = []

    def __call__(self, url: str) -> str:
        self.calls.append(url)
        if url in self.overrides:
            value = self.overrides[url]
            if isinstance(value, Exception):
                raise value
            return value
        if url == SUMMARY_URL:
            return self.summary
        for source in LISTS:
            if url == source.url or url.startswith(source.url + "?page="):
                m = re.search(r"\?page=(\d+)$", url)
                page = int(m.group(1)) if m else 1
                files = self.pages[source.key]
                return read(files[min(page, len(files)) - 1])
        raise AssertionError(f"unexpected URL {url}")
