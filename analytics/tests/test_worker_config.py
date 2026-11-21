"""Worker settings: env only, required URLs fail fast naming the variable (document-stream-worker spec)."""

from __future__ import annotations

import pytest

from investwatch_analytics.config import ConfigError, WorkerSettings

BASE = {"DATABASE_URL": "postgresql://iw_app@postgres/investwatch", "REDIS_URL": "redis://redis:6379/0"}


def test_defaults(monkeypatch):
    for key in ("WORKER_CONSUMER", "STREAM_BLOCK_MS", "CLAIM_MIN_IDLE_MS", "MAX_DELIVERIES", "HEALTH_PORT"):
        monkeypatch.delenv(key, raising=False)
    s = WorkerSettings.from_env(BASE)
    assert (s.database_url, s.redis_url) == (BASE["DATABASE_URL"], BASE["REDIS_URL"])
    assert (s.stream_block_ms, s.claim_min_idle_ms, s.max_deliveries, s.health_port) == (5000, 60000, 5, 8001)
    assert s.max_document_bytes == 2_000_000
    assert s.consumer  # hostname


def test_overrides():
    env = {**BASE, "WORKER_CONSUMER": "w-1", "STREAM_BLOCK_MS": "100", "CLAIM_MIN_IDLE_MS": "10",
           "MAX_DELIVERIES": "2", "HEALTH_PORT": "9000"}
    s = WorkerSettings.from_env(env)
    assert (s.consumer, s.stream_block_ms, s.claim_min_idle_ms, s.max_deliveries, s.health_port) == (
        "w-1", 100, 10, 2, 9000)


@pytest.mark.parametrize("missing", ["DATABASE_URL", "REDIS_URL"])
def test_missing_url_names_the_variable(missing):
    env = {k: v for k, v in BASE.items() if k != missing}
    with pytest.raises(ConfigError, match=missing):
        WorkerSettings.from_env(env)


def test_blank_url_counts_as_missing():
    with pytest.raises(ConfigError, match="DATABASE_URL"):
        WorkerSettings.from_env({**BASE, "DATABASE_URL": "  "})


@pytest.mark.parametrize("key,value", [("MAX_DELIVERIES", "five"), ("MAX_DELIVERIES", "0"), ("HEALTH_PORT", "-1")])
def test_bad_number_names_the_variable(key, value):
    with pytest.raises(ConfigError, match=key):
        WorkerSettings.from_env({**BASE, key: value})
