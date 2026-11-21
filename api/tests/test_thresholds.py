"""Requirements 'Thresholds setting' and 'Risk level derived from the current threshold' (specs/rest-api)."""

from __future__ import annotations

import asyncio
import json

import pytest
import redis as redis_sync

from apiutil import DEAD_REDIS, FakeObjectStore, make_services
from investwatch_api.thresholds import DEFAULTS, KEY, ThresholdStore, risk_level
from openapi_check import assert_response_matches


@pytest.mark.parametrize("score, level", [(0.5, "high"), (0.49, "medium"), (0.3, "medium"), (0.29, "low"),
                                          (1.0, "high"), (0.0, "low")])
def test_boundaries_with_threshold_0_5(score, level):
    assert risk_level(score, 0.5) == level


def _raw(url):
    client = redis_sync.Redis.from_url(url)
    try:
        return client.get(KEY)
    finally:
        client.close()


def test_missing_key_gets_the_defaults(client, redis_clean):
    r = client.get("/api/settings/thresholds")
    assert r.status_code == 200 and r.json() == DEFAULTS
    assert_response_matches("/settings/thresholds", "get", r)
    assert json.loads(_raw(redis_clean)) == DEFAULTS


def test_valid_update_is_stored_as_json(client, redis_clean):
    body = {"M1": 0.6, "M2": 0.7, "M3": 0.7}
    r = client.put("/api/settings/thresholds", json=body)
    assert r.status_code == 200 and r.json() == body
    assert_response_matches("/settings/thresholds", "put", r)
    assert json.loads(_raw(redis_clean)) == body
    assert client.get("/api/settings/thresholds").json() == body


@pytest.mark.parametrize("body", [{"M1": 0.6, "M2": 0.5}, {"M1": 0.6, "M2": 1.5, "M3": 0.7},
                                  {"M1": 0.6, "M2": 0.5, "M3": 0.7, "M4": 0.1}, {"M1": -0.1, "M2": 0.5, "M3": 0.7},
                                  {"M1": "x", "M2": 0.5, "M3": 0.7}])
def test_invalid_update_changes_nothing(client, redis_clean, body):
    before = client.get("/api/settings/thresholds").json()
    r = client.put("/api/settings/thresholds", json=body)
    assert r.status_code == 422 and r.json()["error"] == "validation_error"
    assert json.loads(_raw(redis_clean)) == before


def test_redis_down_on_update(migrated_db):
    from fastapi.testclient import TestClient

    from investwatch_api.app import create_app

    with TestClient(create_app(lambda: make_services(migrated_db.app_url, DEAD_REDIS, FakeObjectStore()))) as c:
        r = c.put("/api/settings/thresholds", json={"M1": 0.1, "M2": 0.1, "M3": 0.1})
    assert r.status_code == 503 and "error" in r.json()


class _FlakyRedis:
    def __init__(self, value):
        self.value, self.down = value, False

    async def get(self, key):
        if self.down:
            raise ConnectionError("down")
        return self.value

    async def set(self, key, value, nx=False):
        if self.down:
            raise ConnectionError("down")
        self.value = value


def test_store_falls_back_to_last_known_values():
    redis = _FlakyRedis(json.dumps({"M1": 0.1, "M2": 0.2, "M3": 0.3}))
    store = ThresholdStore(redis)
    assert asyncio.run(store.current()) == {"M1": 0.1, "M2": 0.2, "M3": 0.3}
    redis.down = True
    assert asyncio.run(store.current()) == {"M1": 0.1, "M2": 0.2, "M3": 0.3}


def test_store_uses_defaults_if_never_read():
    redis = _FlakyRedis(None)
    redis.down = True
    assert asyncio.run(ThresholdStore(redis).current()) == DEFAULTS


def test_malformed_key_falls_back():
    assert asyncio.run(ThresholdStore(_FlakyRedis('{"M1": 2}')).current()) == DEFAULTS
