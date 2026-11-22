"""Bulk status, report export and M2 coverage on the mock server (contract 1.3.0, issue #115, specs/mock-api)."""

from __future__ import annotations

import csv
import io
import uuid

import pytest
from fastapi.testclient import TestClient

from conftest import assert_valid
from iw_mock_server.app import create_app
from iw_mock_server.report import COLUMNS
from iw_mock_server.settings import Settings
from openapi_check import assert_response_matches


@pytest.fixture
def app(contracts_dir):
    app = create_app(Settings(contracts_dir=contracts_dir, replay_interval_s=0, scan_delay_s=0))
    app.state.events = []
    app.state.notify = lambda event_type, data: app.state.events.append({"type": event_type, "data": data})
    return app


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


def _rows(r) -> list[dict]:
    assert r.content.startswith("﻿".encode("utf-8"))
    return list(csv.DictReader(io.StringIO(r.content.decode("utf-8-sig"))))


def test_bulk_change_mixed_ids(client, app):
    a, b = client.get("/api/findings?page_size=2").json()["items"]
    missing = str(uuid.uuid4())
    r = client.post("/api/findings/bulk-status", json={"ids": [a["id"], missing, b["id"]], "status": "closed"})
    assert r.status_code == 200
    assert_response_matches("/findings/bulk-status", "post", r)
    body = r.json()
    assert (body["updated"], body["not_found"]) == (2, 1)
    assert [(x["id"], x["result"]) for x in body["results"]] == [(a["id"], "updated"), (missing, "not_found"),
                                                                 (b["id"], "updated")]
    for f in (a, b):
        got = client.get(f"/api/findings/{f['id']}").json()
        assert got["status"] == "closed" and got["updated_at"] > f["updated_at"]
    assert app.state.events == [{"type": "finding.updated", "data": {"id": a["id"], "status": "closed"}},
                                {"type": "finding.updated", "data": {"id": b["id"], "status": "closed"}}]
    for e in app.state.events:
        assert_valid("events", {**e, "emitted_at": "2026-11-22T00:00:00Z"})


@pytest.mark.parametrize("body", [
    "repeated", {"ids": [], "status": "closed"}, {"ids": ["x"], "status": "closed"}, "null-status", "extra-key",
], ids=["repeated", "empty", "malformed", "null-status", "extra-key"])
def test_bad_bulk_body_changes_nothing(client, app, body):
    f = client.get("/api/findings?page_size=1").json()["items"][0]
    body = {"repeated": {"ids": [f["id"], f["id"]], "status": "closed"},
            "null-status": {"ids": [f["id"]], "status": None},
            "extra-key": {"ids": [f["id"]], "status": "closed", "note": "x"}}.get(body, body) \
        if isinstance(body, str) else body
    r = client.post("/api/findings/bulk-status", json=body)
    assert r.status_code == 422 and r.json()["error"] == "validation_error"
    assert client.get(f"/api/findings/{f['id']}").json()["status"] == f["status"] and app.state.events == []


def test_export_has_the_rows_of_the_list(client):
    listed = client.get("/api/findings?module=M2&page_size=200").json()["items"]
    r = client.get("/api/findings/export?module=M2")
    assert r.status_code == 200 and r.headers["content-type"] == "text/csv; charset=utf-8"
    assert r.headers["content-disposition"].startswith("attachment; ")
    assert r.headers["x-total-count"] == str(len(listed)) and r.headers["x-export-truncated"] == "false"
    rows = _rows(r)
    assert listed and list(rows[0]) == list(COLUMNS)
    assert [(x["id"], x["module"], x["risk_level"]) for x in rows] == [(f["id"], "M2", f["risk_level"]) for f in listed]


@pytest.mark.parametrize("query", ["status=archived", "format=pdf", "sort=title"])
def test_export_invalid_params(client, query):
    assert client.get(f"/api/findings/export?{query}").status_code == 422


def test_summary_has_m2_coverage(client):
    r = client.get("/api/stats/summary")
    assert_response_matches("/stats/summary", "get", r)
    m2 = [f for f in client.get("/api/findings?module=M2&page_size=200").json()["items"]]
    assert r.json()["m2_coverage"] == {"total": len(m2),
                                       "registry_matched": sum(bool((f.get("firm") or {}).get("registry_id"))
                                                               for f in m2)}


def test_m2_coverage_counts_only_matched_m2_findings(contracts_copy):
    import json

    path = contracts_copy / "mocks" / "findings.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data["items"] if isinstance(data, dict) else data
    m2 = [f for f in items if f["module"] == "M2"]
    m2[0]["firm"] = None
    m2[1]["firm"] = {**m2[1]["firm"], "registry_id": None}
    path.write_text(json.dumps(data), encoding="utf-8")
    app = create_app(Settings(contracts_dir=contracts_copy, replay_interval_s=0, scan_delay_s=0))
    with TestClient(app) as c:
        assert c.get("/api/stats/summary").json()["m2_coverage"] == {"total": len(m2), "registry_matched": len(m2) - 2}
