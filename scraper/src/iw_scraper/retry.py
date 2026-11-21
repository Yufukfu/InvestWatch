import random

from iw_scraper.types import Reason

SERVER_ERROR_MIN_STATUS = 500
JITTER_FLOOR = 0.5


def is_transient(reason: Reason, http_status: int | None) -> bool:
    """Only a timeout and an HTTP 5xx are worth retrying; everything else ends the job."""
    if reason is Reason.TIMEOUT:
        return True
    return reason is Reason.HTTP_ERROR and http_status is not None and http_status >= SERVER_ERROR_MIN_STATUS


def backoff_delay(
    failures: int, *, base: float, cap: float, retry_after: float | None, rng: random.Random
) -> float:
    """Exponential backoff with jitter after `failures` failed attempts; `Retry-After` can raise it, never shorten it."""
    ceiling = min(cap, base * 2 ** (failures - 1))
    jittered = ceiling * rng.uniform(JITTER_FLOOR, 1.0)
    return max(jittered, retry_after or 0.0)
