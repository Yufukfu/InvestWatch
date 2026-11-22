"""A `requests.Session` with a default timeout, for the one library that sets none (`youtube-transcript-api`, ADR 0109).

It lives outside `social/` because no social module imports an HTTP client (`test_social_modules_import_no_http_client`).
"""

import requests


class TimeoutSession(requests.Session):
    """Gives every request a connect and read timeout, so a stalled proxy ends the calling thread too."""

    def __init__(self, timeout: float):
        super().__init__()
        self._timeout = timeout

    def request(self, *args, **kwargs):
        if kwargs.get("timeout") is None:
            kwargs["timeout"] = self._timeout
        return super().request(*args, **kwargs)
