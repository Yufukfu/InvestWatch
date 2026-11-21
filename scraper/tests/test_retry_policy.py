import random

import pytest

from iw_scraper.retry import backoff_delay, is_transient
from iw_scraper.types import Reason


@pytest.mark.parametrize(
    ("reason", "status", "expected"),
    [
        (Reason.TIMEOUT, None, True),
        (Reason.HTTP_ERROR, 503, True),
        (Reason.HTTP_ERROR, 500, True),
        (Reason.HTTP_ERROR, 404, False),
        (Reason.HTTP_ERROR, None, False),
        (Reason.HTTP_ERROR, 499, False),
        (Reason.BLOCKED, None, False),
        (Reason.BLOCKED_TARGET, None, False),
        (Reason.PARSE_ERROR, None, False),
    ],
)
def test_only_timeout_and_5xx_are_transient(reason, status, expected):
    assert is_transient(reason, status) is expected


def test_backoff_grows_with_failures_and_stays_inside_jitter_band():
    rng = random.Random(1)
    for failures, ceiling in [(1, 2.0), (2, 4.0), (3, 8.0)]:
        delays = [backoff_delay(failures, base=2.0, cap=300.0, retry_after=None, rng=rng) for _ in range(50)]
        assert min(delays) >= ceiling / 2
        assert max(delays) <= ceiling


def test_backoff_is_capped():
    assert backoff_delay(20, base=2.0, cap=30.0, retry_after=None, rng=random.Random(1)) <= 30.0


def test_retry_after_raises_the_delay():
    assert backoff_delay(1, base=2.0, cap=300.0, retry_after=20.0, rng=random.Random(1)) == 20.0


def test_retry_after_is_clamped_to_its_own_cap():
    delay = backoff_delay(1, base=2.0, cap=30.0, retry_after=1e12, rng=random.Random(1), retry_after_cap=600.0)
    assert delay == 600.0


def test_retry_after_never_shortens_the_delay():
    delay = backoff_delay(3, base=2.0, cap=300.0, retry_after=0.5, rng=random.Random(1))
    assert delay >= 4.0
