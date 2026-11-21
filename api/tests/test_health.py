"""Requirement 'Health' (specs/rest-api) and the contract error shape."""

from __future__ import annotations

import time

from fastapi.testclient import TestClient

from apiutil import DEAD_PG, DEAD_REDIS, FakeObjectStore, make_services
from investwatch_api.app import create_app
from openapi_check import assert_response_matches


def _client(db_url, redis_url, objects):
    return TestClient(create_app(lambda: make_services(db_url, redis_url, objects)))


def test_all_up(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "services": {"api": "ok", "postgres": "ok", "redis": "ok", "minio": "ok"}}
    assert_response_matches("/health", "get", r)


def test_minio_down_answers_within_three_seconds(migrated_db, redis_clean):
    with _client(migrated_db.app_url, redis_clean, FakeObjectStore(slow=True)) as c:
        started = time.monotonic()
        r = c.get("/api/health")
        assert time.monotonic() - started < 3
    assert r.status_code == 200
    assert r.json()["status"] == "degraded" and r.json()["services"]["minio"] == "down"


def test_minio_reports_missing_bucket(migrated_db, redis_clean):
    with _client(migrated_db.app_url, redis_clean, FakeObjectStore(up=False)) as c:
        body = c.get("/api/health").json()
    assert body["status"] == "degraded" and body["services"]["minio"] == "down"


def test_redis_down_is_degraded(migrated_db):
    with _client(migrated_db.app_url, DEAD_REDIS, FakeObjectStore()) as c:
        body = c.get("/api/health").json()
    assert body["status"] == "degraded" and body["services"]["redis"] == "down"


def test_postgres_down(redis_clean):
    with _client(DEAD_PG, redis_clean, FakeObjectStore()) as c:
        r = c.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "down" and r.json()["services"]["postgres"] == "down"


def test_unknown_route_has_the_error_shape(client):
    r = client.get("/api/nope")
    assert r.status_code == 404 and set(r.json()) == {"error"}
