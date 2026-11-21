from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from conftest import assert_valid
from iw_mock_server.app import create_app
from iw_mock_server.settings import Settings
from openapi_check import assert_response_matches

ADMIN = {"X-Mock-Admin": "1"}
NEW_SOURCE = {"name": "Nowe źródło", "platform": "web", "url": "https://new-source.example.com/",
              "source_kind": "unknown", "target_modules": ["M3"], "schedule_cron": None, "active": True}


@pytest.fixture
def client(contracts_dir):
    settings = Settings(contracts_dir=contracts_dir, replay_interval_s=0, scan_delay_s=0)
    with TestClient(create_app(settings)) as c:
        yield c


def a_finding(client, **filters) -> dict:
    query = "&".join(f"{k}={v}" for k, v in filters.items())
    return client.get(f"/api/findings?{query}").json()["items"][0]


def test_patch_status_is_persisted_and_bumps_updated_at(client):
    f = a_finding(client, status="new")

    r = client.patch(f"/api/findings/{f['id']}", json={"status": "confirmed", "note": "sprawdzone"})

    assert r.status_code == 200
    assert_response_matches("/findings/{id}", "patch", r)
    assert r.json()["status"] == "confirmed" and r.json()["note"] == "sprawdzone"
    assert r.json()["updated_at"] > f["updated_at"]
    assert client.get(f"/api/findings/{f['id']}").json()["status"] == "confirmed"


@pytest.mark.parametrize("body", [{"status": "approved"}, {}, {"unknown": 1}, {"status": None}])
def test_patch_rejects_invalid_body_and_keeps_the_finding(client, body):
    f = a_finding(client)

    r = client.patch(f"/api/findings/{f['id']}", json=body)

    assert r.status_code == 422
    assert client.get(f"/api/findings/{f['id']}").json()["status"] == f["status"]


def test_patch_unknown_finding_is_404(client):
    assert client.patch(f"/api/findings/{uuid.uuid4()}", json={"status": "closed"}).status_code == 404


def test_threshold_change_recomputes_risk_level_and_calibration(client):
    r = client.put("/api/settings/thresholds", json={"M1": 0.6, "M2": 0.9, "M3": 0.7})

    assert r.status_code == 200
    assert_response_matches("/settings/thresholds", "put", r)
    for item in client.get("/api/findings?module=M2").json()["items"]:
        expected = "high" if item["score"] >= 0.9 else "medium" if item["score"] >= 0.7 else "low"
        assert item["risk_level"] == expected
    assert client.get("/api/calibration?module=M2").json()["current_threshold"] == 0.9


@pytest.mark.parametrize("body", [{"M1": 0.6, "M2": 1.5, "M3": 0.7}, {"M1": 0.6, "M3": 0.7},
                                  {"M1": 0.6, "M2": 0.5, "M3": 0.7, "M4": 0.1}])
def test_invalid_thresholds_are_rejected_and_unchanged(client, body):
    before = client.get("/api/settings/thresholds").json()

    assert client.put("/api/settings/thresholds", json=body).status_code == 422
    assert client.get("/api/settings/thresholds").json() == before


def test_add_and_edit_source(client):
    r = client.post("/api/sources", json=NEW_SOURCE)

    assert r.status_code == 201
    created = r.json()
    assert_valid("source", created)
    assert uuid.UUID(created["id"]).version == 4
    assert created["id"] in {s["id"] for s in client.get("/api/sources").json()["items"]}

    r = client.patch(f"/api/sources/{created['id']}", json={"active": False})

    assert r.status_code == 200
    assert r.json()["active"] is False
    assert_valid("source", r.json())


@pytest.mark.parametrize("body", [{**NEW_SOURCE, "platform": "myspace"}, {"name": "brak reszty"},
                                  {**NEW_SOURCE, "target_modules": []}])
def test_invalid_source_is_422(client, body):
    assert client.post("/api/sources", json=body).status_code == 422


def test_patch_unknown_source_is_404(client):
    assert client.patch(f"/api/sources/{uuid.uuid4()}", json={"active": False}).status_code == 404


def test_scan_existing_source_is_accepted(client):
    source_id = client.get("/api/sources").json()["items"][0]["id"]

    r = client.post("/api/scans", json={"source_id": source_id})

    assert r.status_code == 202
    assert r.json() == {"queued": True, "source_id": source_id}


def test_scan_unknown_source_is_404(client):
    assert client.post("/api/scans", json={"source_id": str(uuid.uuid4())}).status_code == 404


def test_reset_restores_original_data(client):
    f = a_finding(client, status="new")
    client.patch(f"/api/findings/{f['id']}", json={"status": "closed"})
    client.put("/api/settings/thresholds", json={"M1": 0.1, "M2": 0.1, "M3": 0.1})
    client.post("/api/sources", json=NEW_SOURCE)

    assert client.post("/__mock/reset", headers=ADMIN).status_code == 200

    assert client.get(f"/api/findings/{f['id']}").json()["status"] == "new"
    assert client.get("/api/settings/thresholds").json() == {"M1": 0.6, "M2": 0.5, "M3": 0.7}
    assert len(client.get("/api/sources").json()["items"]) == 4


@pytest.mark.parametrize("body", [{**NEW_SOURCE, "target_modules": ["M1", "M1"]}, {**NEW_SOURCE, "url": "not a url"}])
def test_source_breaking_the_schema_is_422(client, body):
    # source.schema.json: target_modules has uniqueItems, url is format uri
    assert client.post("/api/sources", json=body).status_code == 422


def test_patch_source_with_duplicate_modules_is_422_and_unchanged(client):
    source = client.get("/api/sources").json()["items"][0]

    r = client.patch(f"/api/sources/{source['id']}", json={"target_modules": ["M2", "M2"]})

    assert r.status_code == 422
    assert client.get("/api/sources").json()["items"][0]["target_modules"] == source["target_modules"]


@pytest.mark.parametrize("url", ["https://Example.com", "https://example.com/path?q=1"])
def test_source_url_is_stored_as_sent(client, url):
    created = client.post("/api/sources", json={**NEW_SOURCE, "url": url}).json()
    assert created["url"] == url

    patched = client.patch(f"/api/sources/{created['id']}", json={"url": url + "#x"}).json()
    assert patched["url"] == url + "#x"


@pytest.mark.parametrize("url", [" https://x.example.com ", "https://x.example.com\n", "https://x.example.com/é",
                                 "https://x.example.com/a b"])
def test_source_url_that_is_not_a_uri_is_422(client, url):
    # HttpUrl strips and percent-encodes, but the url is stored as sent, so it must already be a valid uri
    assert client.post("/api/sources", json={**NEW_SOURCE, "url": url}).status_code == 422


@pytest.mark.parametrize("path", ["/__mock/reset", "/__mock/emit"])
@pytest.mark.parametrize("headers", [{}, {"X-Mock-Admin": ""}])
def test_mock_helpers_need_the_admin_header(client, path, headers):
    # a body-less POST without custom headers is a "simple" request any web page could send
    f = a_finding(client, status="new")
    client.patch(f"/api/findings/{f['id']}", json={"status": "closed"})

    r = client.post(path, headers=headers)

    assert r.status_code == 403
    assert "error" in r.json()
    assert client.get(f"/api/findings/{f['id']}").json()["status"] == "closed"


@pytest.mark.parametrize("module", ["M1", "M2", "M3"])
@pytest.mark.parametrize("value", [True, "0.5"])
def test_threshold_must_be_a_json_number(client, module, value):
    body = {"M1": 0.6, "M2": 0.5, "M3": 0.7, module: value}
    assert client.put("/api/settings/thresholds", json=body).status_code == 422


def test_integer_thresholds_are_numbers(client):
    r = client.put("/api/settings/thresholds", json={"M1": 1, "M2": 0, "M3": 0.7})

    assert r.status_code == 200
    assert r.json() == {"M1": 1.0, "M2": 0.0, "M3": 0.7}


@pytest.mark.parametrize(("field", "limit"), [("name", 500), ("schedule_cron", 200)])
def test_source_text_fields_have_a_length_limit(client, field, limit):
    assert client.post("/api/sources", json={**NEW_SOURCE, field: "x" * limit}).status_code == 201
    assert client.post("/api/sources", json={**NEW_SOURCE, field: "x" * (limit + 1)}).status_code == 422
    source_id = client.get("/api/sources").json()["items"][0]["id"]
    assert client.patch(f"/api/sources/{source_id}", json={field: "x" * (limit + 1)}).status_code == 422


def test_note_has_a_length_limit(client):
    f = a_finding(client)

    assert client.patch(f"/api/findings/{f['id']}", json={"note": "x" * 10_000}).status_code == 200
    assert client.patch(f"/api/findings/{f['id']}", json={"note": "x" * 10_001}).status_code == 422
