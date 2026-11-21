"""Optional live check of the KNF pages: `pytest -m live`. Skipped by default and on CI (pyproject addopts).

It only asserts that each list still has its records and labels, so a KNF layout change shows before a refresh.
"""

from __future__ import annotations

import pytest

from investwatch_analytics.knf.fetch import LISTS, HttpFetcher, check_summary
from investwatch_analytics.knf.parse import NAME_LABELS, parse_page

pytestmark = pytest.mark.live


@pytest.fixture(scope="module")
def fetcher():
    return HttpFetcher()


def test_summary_still_links_the_lists(fetcher):
    check_summary(fetcher)


@pytest.mark.parametrize("source", LISTS, ids=[s.key for s in LISTS])
def test_first_page_has_records_with_a_name_label(fetcher, source):
    records = parse_page(fetcher(source.url), where=source.key)
    assert records and all(any(label in r.cells for label in NAME_LABELS) for r in records)
