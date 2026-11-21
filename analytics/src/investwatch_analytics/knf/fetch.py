"""Fetch the KNF list pages (design decision 1). Tests pass a fake `fetcher`; nothing here runs in unit tests
against the network."""

from __future__ import annotations

import logging
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass

from . import KnfError
from .parse import RawRecord, parse_page

log = logging.getLogger(__name__)

HOST = "https://www.knf.gov.pl"
BASE_PATH = "/podmioty/Podmioty_rynku_kapitalowego/Firmy_inwestycyjne_i_Agenci_firm_inwestycyjnych"
SUMMARY_URL = HOST + BASE_PATH
MAX_PAGES = 100
MAX_SKIPPED_SHARE = 0.05
MAX_BYTES = 5_000_000  # a real list page is under 200 KB
USER_AGENT = "InvestWatch-registry-loader/1.0 (HackNation UKNF challenge; manual run)"

Fetcher = Callable[[str], str]


@dataclass(frozen=True)
class ListSource:
    key: str
    path: str
    type: str

    @property
    def url(self) -> str:
        return HOST + BASE_PATH + self.path

    def page_url(self, page: int) -> str:
        return self.url if page == 1 else f"{self.url}?page={page}"


#: The four lists of annexes 1 and 2, in type precedence order (design decision 4).
LISTS = (
    ListSource("brokerage_houses", "/domy_maklerskie", "brokerage_house"),
    ListSource("banks", "/Banki_prowadzace_dzialalnosc_maklerska", "brokerage_bank"),
    ListSource("branches", "/notyfikowane_firmy_inwestycyjne_oddzialy", "foreign_branch"),
    ListSource("no_branch", "/notyfikowane_zagraniczne_firmy_inwestycyjne", "foreign_no_branch"),
)


class KnfOnlyRedirects(urllib.request.HTTPRedirectHandler):
    """Follow a redirect only to another https page on the KNF host; anything else fails the run."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not newurl.startswith(HOST + "/"):
            raise KnfError("fetch_failed", f"{req.full_url}: redirect to {newurl} refused (not a KNF URL)")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class HttpFetcher:
    """GET with a timeout, at most one request per `min_interval` seconds and `attempts` tries with backoff.
    Only URLs on the KNF host are fetched."""

    def __init__(self, *, timeout: float = 30.0, attempts: int = 3, min_interval: float = 0.5,
                 sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic,
                 opener: Callable | None = None):
        self.timeout, self.attempts, self.min_interval = timeout, attempts, min_interval
        self._sleep, self._clock = sleep, clock
        self._open = opener or urllib.request.build_opener(KnfOnlyRedirects()).open
        self._last: float | None = None

    def __call__(self, url: str) -> str:
        if not url.startswith(HOST + "/"):
            raise KnfError("fetch_failed", f"{url}: not a KNF URL")
        detail = "no attempt"
        for attempt in range(1, self.attempts + 1):
            self._throttle()
            try:
                request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                with self._open(request, timeout=self.timeout) as response:
                    body = response.read(MAX_BYTES + 1)
                if len(body) > MAX_BYTES:
                    raise KnfError("fetch_failed", f"{url}: response larger than {MAX_BYTES} bytes")
                return body.decode("utf-8")
            except urllib.error.HTTPError as exc:
                detail = f"HTTP {exc.code}"
                exc.close()
            except (urllib.error.URLError, TimeoutError, OSError, UnicodeDecodeError) as exc:
                detail = f"{type(exc).__name__}: {getattr(exc, 'reason', exc)}"
            log.warning("knf fetch failed", extra={"url": url, "attempt": attempt, "error": detail})
            if attempt < self.attempts:
                self._sleep(2 ** (attempt - 1))
        raise KnfError("fetch_failed", f"{url}: {detail} after {self.attempts} attempts")

    def _throttle(self) -> None:
        now = self._clock()
        if self._last is not None and (wait := self._last + self.min_interval - now) > 0:
            self._sleep(wait)
            now += wait
        self._last = now


def check_summary(fetcher: Fetcher) -> None:
    """The summary page must still link every list (`list_moved` otherwise)."""
    html = fetcher(SUMMARY_URL)
    for source in LISTS:
        if f'href="{BASE_PATH}{source.path}"' not in html and f'href="{source.url}"' not in html:
            raise KnfError("list_moved", f"{SUMMARY_URL} no longer links {BASE_PATH}{source.path}")


@dataclass(frozen=True)
class FetchedList:
    source: ListSource
    records: list[RawRecord]
    skipped: int  # records without a name, left out
    pages: int


def fetch_list(fetcher: Fetcher, source: ListSource, *, max_pages: int = MAX_PAGES) -> FetchedList:
    """All records of one list. KNF answers any page past the last with the last page again, so the list ends
    at the first page that adds no new record; more than `max_pages` pages means the layout changed.
    A record without a name is skipped; more than MAX_SKIPPED_SHARE of a list skipped fails the run."""
    records: list[RawRecord] = []
    previous: list[str] | None = None
    # One page more than the cap: page max_pages + 1 must be the repeat of the last real page.
    for page in range(1, max_pages + 2):
        page_records = parse_page(fetcher(source.page_url(page)), where=source.key, page=page)
        fingerprints = [r.fingerprint for r in page_records]
        # The list ends at an empty page or one that repeats the previous page. Identical records on
        # different pages (KNF lists some firms twice) are all kept; merging is build.py's job.
        if not page_records or fingerprints == previous:
            break
        previous = fingerprints
        records.extend(page_records)
    else:
        raise KnfError("layout_changed", f"{source.key}: still new records after {max_pages} pages")
    named = [r for r in records if r.name_lines]
    skipped = len(records) - len(named)
    if skipped > MAX_SKIPPED_SHARE * len(records):
        raise KnfError("layout_changed", f"{source.key}: {skipped} of {len(records)} records have no name")
    if skipped:
        log.warning("knf records without a name skipped", extra={"list": source.key, "skipped": skipped})
    return FetchedList(source, named, skipped, page - 1)


def fetch_all(fetcher: Fetcher, *, max_pages: int = MAX_PAGES) -> dict[str, FetchedList]:
    check_summary(fetcher)
    return {source.key: fetch_list(fetcher, source, max_pages=max_pages) for source in LISTS}
