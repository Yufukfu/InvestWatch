"""Statistics, calibration, sources, scans, screenshots and route coverage (specs/rest-api)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import redis as redis_sync
import yaml
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert, select

from apiutil import DEAD_REDIS, FakeObjectStore, make_services
from conftest import CONTRACTS_DIR, assert_contract_valid
from dbutil import document_row, finding_row, source_row
from investwatch_api.app import create_app
from investwatch_api.db.tables import calibration_points, documents, findings, sources
from investwatch_api.thresholds import DEFAULTS, risk_level
from openapi_check import assert_response_matches


def _insert(url, table, rows):
    engine = create_engine(url)
    with engine.begin() as conn:
        for r in rows:
            conn.execute(insert(table).values(r))
    engine.dispose()


def _rows(url, table):
    engine = create_engine(url)
    with engine.connect() as conn:
        out = conn.execute(select(table)).mappings().all()
    engine.dispose()
    return out


def test_every_contract_path_has_a_route(client):
    spec = yaml.safe_load((CONTRACTS_DIR / "openapi.yaml").read_text(encoding="utf-8"))
    import re

    norm = lambda path: re.sub(r"\{[a-z_]+\}", "{x}", path)
    served = {(norm(p.removeprefix("/api")), m) for p, ops in client.app.openapi()["paths"].items() for m in ops}
    wanted = {(norm(p), m) for p, ops in spec["paths"].items() for m in ops if m != "parameters"}
    assert len(spec["paths"]) == 11
    assert wanted <= served, sorted(wanted - served)


# --- statistics ------------------------------------------------------------------------------

def test_summary_on_an_empty_database(client):
    r = client.get("/api/stats/summary")
    assert_response_matches("/stats/summary", "get", r)
    body = r.json()
    assert body["total"] == 0 and body["last_scan_at"] is None
    assert body["by_module"] == {"M1": 0, "M2": 0, "M3": 0}
    assert set(body["by_status"]) == {"new", "in_review", "confirmed", "false_positive", "closed"}
    assert body["by_risk_level"] == {"high": 0, "medium": 0, "low": 0} and body["by_platform"] == {}


def test_summary_counts_the_mocks(client, seeded):
    body = client.get("/api/stats/summary").json()
    finds = seeded["findings"]
    assert body["total"] == len(finds)
    for m in ("M1", "M2", "M3"):
        assert body["by_module"][m] == sum(f["module"] == m for f in finds)
    for level in ("high", "medium", "low"):
        assert body["by_risk_level"][level] == sum(risk_level(f["score"], DEFAULTS[f["module"]]) == level
                                                   for f in finds)
    runs = [s["last_run_at"] for s in seeded["sources"] if s.get("last_run_at")]
    assert body["last_scan_at"] == max(runs)


def test_day_buckets_are_zero_filled(client, migrated_db):
    doc = document_row()
    _insert(migrated_db.app_url, documents, [doc])
    t = datetime(2026, 11, 21, 10, 30, tzinfo=timezone.utc)
    _insert(migrated_db.app_url, findings, [finding_row(doc["id"], module="M2", detected_at=t, updated_at=t)])
    r = client.get("/api/stats/trend", params={"bucket": "day", "date_from": "2026-11-20T00:00:00Z",
                                                "date_to": "2026-11-21T23:59:59Z"})
    assert_response_matches("/stats/trend", "get", r)
    assert r.json() == {"bucket": "day", "points": [
        {"t": "2026-11-20T00:00:00Z", "M1": 0, "M2": 0, "M3": 0},
        {"t": "2026-11-21T00:00:00Z", "M1": 0, "M2": 1, "M3": 0}]}


def test_day_buckets_start_at_midnight_utc(client):
    r = client.get("/api/stats/trend", params={"bucket": "day", "date_from": "2026-11-20T15:00:00+02:00",
                                                "date_to": "2026-11-21T10:00:00Z"})
    assert [p["t"] for p in r.json()["points"]] == ["2026-11-20T00:00:00Z", "2026-11-21T00:00:00Z"]


def test_hour_buckets_default_to_the_last_24_hours(client):
    points = client.get("/api/stats/trend").json()["points"]
    assert len(points) in (24, 25) and all(p["t"].endswith(":00:00Z") for p in points)


def test_module_filter_keeps_the_shape(client, migrated_db):
    docs = [document_row(), document_row()]
    _insert(migrated_db.app_url, documents, docs)
    now = datetime.now(timezone.utc)
    _insert(migrated_db.app_url, findings, [finding_row(docs[0]["id"], module="M1", detected_at=now, updated_at=now),
                                            finding_row(docs[1]["id"], module="M2", detected_at=now, updated_at=now)])
    points = client.get("/api/stats/trend", params={"module": "M1"}).json()["points"]
    assert all(set(p) == {"t", "M1", "M2", "M3"} and p["M2"] == 0 and p["M3"] == 0 for p in points)
    assert sum(p["M1"] for p in points) == 1


def test_trend_risk_filter_uses_the_same_rule(client, migrated_db):
    docs = [document_row(), document_row()]
    _insert(migrated_db.app_url, documents, docs)
    now = datetime.now(timezone.utc)
    _insert(migrated_db.app_url, findings, [finding_row(docs[0]["id"], module="M2", score=0.5, detected_at=now, updated_at=now),
                                            finding_row(docs[1]["id"], module="M2", score=0.2, detected_at=now, updated_at=now)])
    points = client.get("/api/stats/trend", params={"risk_level": "high"}).json()["points"]
    assert sum(p["M2"] for p in points) == 1


@pytest.mark.parametrize("params", [{"date_from": "2026-11-22T00:00:00Z", "date_to": "2026-11-21T00:00:00Z"},
                                    {"date_from": "2000-01-01T00:00:00Z", "date_to": "2026-11-21T00:00:00Z"},
                                    {"bucket": "week"}])
def test_trend_rejects_bad_ranges(client, params):
    assert client.get("/api/stats/trend", params=params).status_code == 422


# --- calibration -----------------------------------------------------------------------------

def _point(run, th, at, module="M2", f1=None):
    return dict(run_id=run, module=module, threshold=th, tp=3, fp=1, fn=1, tn=5, precision=0.75, recall=0.75,
                f1=f1, labeled_samples=10, computed_at=at)


def test_latest_run(client, migrated_db):
    old, new, t = uuid.uuid4(), uuid.uuid4(), datetime.now(timezone.utc)
    _insert(migrated_db.app_url, calibration_points,
            [_point(old, 0.5, t - timedelta(hours=1)), _point(new, 0.7, t, f1=0.75), _point(new, 0.4, t)])
    r = client.get("/api/calibration", params={"module": "M2"})
    assert_response_matches("/calibration", "get", r)
    body = r.json()
    assert [p["threshold"] for p in body["points"]] == [0.4, 0.7]
    assert body["labeled_samples"] == 10 and body["current_threshold"] == DEFAULTS["M2"]
    assert "f1" not in body["points"][0] and body["points"][1]["f1"] == 0.75


def test_no_run_yet(client):
    client.put("/api/settings/thresholds", json={"M1": 0.6, "M2": 0.5, "M3": 0.65})
    body = client.get("/api/calibration", params={"module": "M3"}).json()
    assert body == {"module": "M3", "current_threshold": 0.65, "labeled_samples": 0, "points": []}


@pytest.mark.parametrize("params", [{}, {"module": "M4"}])
def test_module_missing_or_unknown(client, params):
    assert client.get("/api/calibration", params=params).status_code == 422


# --- sources ---------------------------------------------------------------------------------

NEW_SOURCE = {"name": "Alfa", "platform": "web", "url": "https://alfa.example/", "source_kind": "firm_own",
              "target_modules": ["M2"]}


def test_create_a_source(client, migrated_db):
    r = client.post("/api/sources", json=NEW_SOURCE)
    assert r.status_code == 201
    assert_response_matches("/sources", "post", r)
    body = r.json()
    assert body["active"] is True and body["documents_count"] == 0 and uuid.UUID(body["id"]).version == 4
    assert [str(s["id"]) for s in _rows(migrated_db.app_url, sources)] == [body["id"]]


@pytest.mark.parametrize("missing", ["name", "platform", "url", "source_kind", "target_modules"])
def test_create_with_missing_field(client, migrated_db, missing):
    body = {k: v for k, v in NEW_SOURCE.items() if k != missing}
    assert client.post("/api/sources", json=body).status_code == 422
    assert _rows(migrated_db.app_url, sources) == []


@pytest.mark.parametrize("over", [{"target_modules": ["M1", "M1"]}, {"url": "not a url"}, {"platform": "myspace"},
                                  {"extra": 1}])
def test_create_with_invalid_value(client, over):
    assert client.post("/api/sources", json={**NEW_SOURCE, **over}).status_code == 422


def test_list_sources_with_counts(client, seeded):
    r = client.get("/api/sources")
    assert_response_matches("/sources", "get", r)
    counts = {s["id"]: s["documents_count"] for s in r.json()["items"]}
    for s in seeded["sources"]:
        assert counts[s["id"]] == sum(d.get("source_id") == s["id"] for d in seeded["documents"])


def test_deactivate_a_source(client):
    created = client.post("/api/sources", json=NEW_SOURCE).json()
    r = client.patch(f"/api/sources/{created['id']}", json={"active": False})
    assert r.status_code == 200
    assert_response_matches("/sources/{id}", "patch", r)
    assert {k: v for k, v in r.json().items() if k != "active"} == {k: v for k, v in created.items() if k != "active"}
    assert r.json()["active"] is False


def test_schedule_can_be_cleared(client):
    created = client.post("/api/sources", json={**NEW_SOURCE, "schedule_cron": "0 */6 * * *"}).json()
    assert "schedule_cron" not in client.patch(f"/api/sources/{created['id']}", json={"schedule_cron": None}).json()


@pytest.mark.parametrize("body", [{}, {"name": None}, {"target_modules": []}, {"active": None}])
def test_invalid_patch(client, body):
    created = client.post("/api/sources", json=NEW_SOURCE).json()
    assert client.patch(f"/api/sources/{created['id']}", json=body).status_code == 422
    assert client.get("/api/sources").json()["items"] == [created]


def test_unknown_source_patch(client):
    r = client.patch(f"/api/sources/{uuid.uuid4()}", json={"active": False})
    assert r.status_code == 404 and set(r.json()) == {"error"}


# --- scans -----------------------------------------------------------------------------------

def _stream(url):
    client = redis_sync.Redis.from_url(url, decode_responses=True)
    try:
        return client.xrange("iw:scan-requests")
    finally:
        client.close()


def test_scan_queued(client, redis_clean, migrated_db):
    src = source_row()
    _insert(migrated_db.app_url, sources, [src])
    r = client.post("/api/scans", json={"source_id": str(src["id"])})
    assert r.status_code == 202 and r.json() == {"queued": True, "source_id": str(src["id"])}
    assert_response_matches("/scans", "post", r)
    entries = _stream(redis_clean)
    assert len(entries) == 1
    assert_contract_valid("events", entries[0][1])
    assert entries[0][1]["source_id"] == str(src["id"])


def test_scan_unknown_source(client, redis_clean):
    r = client.post("/api/scans", json={"source_id": str(uuid.uuid4())})
    assert r.status_code == 404 and _stream(redis_clean) == []


def test_scan_redis_down(migrated_db, app_engine):
    src = source_row()
    _insert(migrated_db.app_url, sources, [src])
    with TestClient(create_app(lambda: make_services(migrated_db.app_url, DEAD_REDIS, FakeObjectStore()))) as c:
        r = c.post("/api/scans", json={"source_id": str(src["id"])})
    assert r.status_code == 503 and "error" in r.json()


# --- screenshots -----------------------------------------------------------------------------

PNG = b"\x89PNG\r\n\x1a\nfake"


def test_screenshot_exists(client, migrated_db, objects):
    doc = document_row(payload={"screenshots": {"desktop": "shot/x/desktop.png"}})
    _insert(migrated_db.app_url, documents, [doc])
    objects.objects["shot/x/desktop.png"] = PNG
    r = client.get(f"/api/documents/{doc['id']}/screenshot/desktop")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png" and r.content == PNG
    assert objects.requested == ["shot/x/desktop.png"]


def test_no_such_screenshot(client, migrated_db, objects):
    doc = document_row(payload={"screenshots": {"desktop": "shot/y/desktop.png", "mobile": None}})
    _insert(migrated_db.app_url, documents, [doc])
    for path in (f"/api/documents/{uuid.uuid4()}/screenshot/desktop",   # no document
                 f"/api/documents/{doc['id']}/screenshot/mobile",       # no key for the viewport
                 f"/api/documents/{doc['id']}/screenshot/desktop"):     # object missing in MinIO
        r = client.get(path)
        assert r.status_code == 404 and set(r.json()) == {"error"}, path
    assert objects.requested == ["shot/y/desktop.png"]  # the key came from the row only


def test_viewport_not_in_the_enum(client):
    assert client.get(f"/api/documents/{uuid.uuid4()}/screenshot/watch").status_code == 422


def test_minio_down(migrated_db, app_engine, redis_clean):
    doc = document_row(payload={"screenshots": {"tablet": "shot/z/tablet.png"}})
    _insert(migrated_db.app_url, documents, [doc])
    with TestClient(create_app(lambda: make_services(migrated_db.app_url, redis_clean, FakeObjectStore(up=False)))) as c:
        r = c.get(f"/api/documents/{doc['id']}/screenshot/tablet")
    assert r.status_code == 503 and "error" in r.json()
