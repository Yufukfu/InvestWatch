"""MinioStore against an unreachable endpoint: fails fast (no five-retry backoff) and maps errors."""

from __future__ import annotations

import asyncio
import time

import pytest

from investwatch_api.objectstore import MinioStore, ObjectStoreError


def _dead_store() -> MinioStore:
    return MinioStore("127.0.0.1:1", access_key="x", secret_key="y", bucket="iw-raw")


def test_ping_fails_fast_when_unreachable():
    started = time.monotonic()
    assert asyncio.run(_dead_store().ping()) is False
    assert time.monotonic() - started < 3


def test_get_raises_object_store_error_when_unreachable():
    with pytest.raises(ObjectStoreError):
        asyncio.run(_dead_store().get("shot/x/desktop.png"))
