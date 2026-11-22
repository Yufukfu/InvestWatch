"""Bulk status change, CSV report export and M2 coverage (contract 1.3.0, issue #115, specs/rest-api)."""

from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from apiutil import DEAD_REDIS, FakeObjectStore, make_services
from conftest import assert_contract_valid
from dbutil import document_row, finding_row
from investwatch_api.app import create_app
from investwatch_api.db.mapping import parse_time
from investwatch_api.report import COLUMNS
from openapi_check import assert_response_matches
from test_findings import Events, _insert, _stored


def _findings(url, *overs):
    t = datetime.now(timezone.utc)
    docs = [document_row() for _ in overs]
    finds = [finding_row(d["id"], detected_at=t - timedelta(minutes=i), updated_at=t - timedelta(hours=1), **o)
             for i, (d, o) in enumerate(zip(docs, overs))]
    _insert(url, docs, finds)
    return finds


def _rows(r) -> list[dict]:
    assert r.content.startswith("﻿".encode("utf-8"))
    return list(csv.DictReader(io.StringIO(r.content.decode("utf-8-sig"))))


FIRM = {"name": "Alfa DM", "registry_id": str(uuid.uuid4()), "registry_type": "brokerage_house", "authorized": True}


# --- M2 coverage -----------------------------------------------------------------------------

def test_m2_coverage_counts_matched_m2_findings_only(client, migrated_db):
    _findings(migrated_db.app_url, {"firm": FIRM}, {"firm": {**FIRM, "registry_id": str(uuid.uuid4())}},
              {"firm": None}, {"module": "M2", "firm": {"name": "Nieznana", "registry_id": None}},
              {"module": "M1", "firm": FIRM})
    r = client.get("/api/stats/summary")
    assert_response_matches("/stats/summary", "get", r)
    assert r.json()["m2_coverage"] == {"total": 4, "registry_matched": 2}
    assert r.json()["by_module"] == {"M1": 1, "M2": 4, "M3": 0}


def test_m2_coverage_on_an_empty_database(client):
    assert client.get("/api/stats/summary").json()["m2_coverage"] == {"total": 0, "registry_matched": 0}


def test_m2_coverage_of_the_mocks(client, seeded):
    m2 = [f for f in seeded["findings"] if f["module"] == "M2"]
    got = client.get("/api/stats/summary").json()["m2_coverage"]
    assert got == {"total": len(m2), "registry_matched": sum(bool((f.get("firm") or {}).get("registry_id")) for f in m2)}


# --- bulk status -----------------------------------------------------------------------------

def test_bulk_status_mixed_ids(client, migrated_db, redis_clean):
    a, b, other = _findings(migrated_db.app_url, {}, {"status": "in_review"}, {})
    missing = uuid.uuid4()
    with Events(redis_clean) as events:
        r = client.post("/api/findings/bulk-status",
                        json={"ids": [str(a["id"]), str(missing), str(b["id"])], "status": "confirmed"})
        got = events.collect()
    assert r.status_code == 200
    assert_response_matches("/findings/bulk-status", "post", r)
    body = r.json()
    assert (body["updated"], body["not_found"]) == (2, 1)
    assert [(x["id"], x["result"]) for x in body["results"]] == [
        (str(a["id"]), "updated"), (str(missing), "not_found"), (str(b["id"]), "updated")]
    assert body["results"][1]["finding"] is None
    for item, f in ((body["results"][0], a), (body["results"][2], b)):
        assert item["finding"]["status"] == "confirmed" and item["finding"]["risk_level"]
        assert parse_time(item["finding"]["updated_at"]) > f["updated_at"]
        stored = _stored(migrated_db, f["id"])
        assert stored["status"] == "confirmed" and stored["updated_at"] > f["updated_at"]
    assert _stored(migrated_db, other["id"])["status"] == "new"
    assert sorted((e["type"], e["data"]["id"], e["data"]["status"]) for e in got) == sorted(
        [("finding.updated", str(a["id"]), "confirmed"), ("finding.updated", str(b["id"]), "confirmed")])
    for e in got:
        assert_contract_valid("events", e)


def test_bulk_status_all_unknown(client, migrated_db, redis_clean):
    with Events(redis_clean) as events:
        r = client.post("/api/findings/bulk-status", json={"ids": [str(uuid.uuid4())], "status": "closed"})
        got = events.collect(0.3)
    assert r.status_code == 200 and (r.json()["updated"], r.json()["not_found"]) == (0, 1) and got == []


def _bad_bodies():
    one = "11111111-1111-4111-8111-111111111111"
    return {
        "no-ids": {"status": "closed"}, "empty-ids": {"ids": [], "status": "closed"},
        "too-many": {"ids": [str(uuid.uuid4()) for _ in range(201)], "status": "closed"},
        "repeated": {"ids": [one, one], "status": "closed"}, "malformed": {"ids": ["nope"], "status": "closed"},
        "no-status": {"ids": [one]}, "null-status": {"ids": [one], "status": None},
        "bad-status": {"ids": [one], "status": "archived"}, "extra-key": {"ids": [one], "status": "closed", "note": "x"},
    }


@pytest.mark.parametrize("name", list(_bad_bodies()))
def test_bulk_status_invalid_bodies(client, migrated_db, redis_clean, name):
    f, = _findings(migrated_db.app_url, {})
    body = _bad_bodies()[name]
    if "ids" in body and body["ids"] and body["ids"][0].startswith("1111"):
        body["ids"] = [str(f["id"])] * len(body["ids"])
    with Events(redis_clean) as events:
        r = client.post("/api/findings/bulk-status", json=body)
        got = events.collect(0.3)
    assert r.status_code == 422 and r.json()["error"] == "validation_error"
    assert _stored(migrated_db, f["id"])["status"] == "new" and got == []


def test_bulk_status_accepts_200_ids(client, migrated_db):
    f, = _findings(migrated_db.app_url, {})
    ids = [str(f["id"])] + [str(uuid.uuid4()) for _ in range(199)]
    r = client.post("/api/findings/bulk-status", json={"ids": ids, "status": "closed"})
    assert r.status_code == 200 and (r.json()["updated"], r.json()["not_found"]) == (1, 199)


def test_bulk_status_redis_down_after_commit(migrated_db, app_engine, caplog):
    f, = _findings(migrated_db.app_url, {})
    with TestClient(create_app(lambda: make_services(migrated_db.app_url, DEAD_REDIS, FakeObjectStore()))) as c:
        r = c.post("/api/findings/bulk-status", json={"ids": [str(f["id"])], "status": "closed"})
    assert r.status_code == 200 and r.json()["updated"] == 1
    assert _stored(migrated_db, f["id"])["status"] == "closed"
    assert any(rec.levelname == "ERROR" and "publish" in rec.getMessage() for rec in caplog.records)


# --- report export ---------------------------------------------------------------------------

def test_export_has_the_rows_of_the_list(client, seeded):
    params = {"sort": "-score"}
    listed = client.get("/api/findings", params={**params, "page_size": 200}).json()["items"]
    r = client.get("/api/findings/export", params=params)
    assert r.status_code == 200 and r.headers["content-type"] == "text/csv; charset=utf-8"
    assert r.headers["content-disposition"].startswith('attachment; filename="investwatch-findings-')
    assert r.headers["x-total-count"] == str(len(listed)) and r.headers["x-export-truncated"] == "false"
    rows = _rows(r)
    assert list(rows[0]) == list(COLUMNS)
    assert [(x["id"], x["module"], x["status"], x["risk_level"], float(x["score"])) for x in rows] == [
        (f["id"], f["module"], f["status"], f["risk_level"], f["score"]) for f in listed]


def test_export_applies_the_same_filters(client, migrated_db):
    a, _, c = _findings(migrated_db.app_url, {"rules": [
        {"rule_id": "R1", "name": "a", "result": "fail", "severity": "high"},
        {"rule_id": "R2", "name": "b", "result": "pass", "severity": "low"},
        {"rule_id": "R7", "name": "c", "result": "fail", "severity": "low"}], "firm": FIRM},
        {"module": "M1"}, {"status": "closed"})
    params = {"module": "M2", "status": "new"}
    listed = client.get("/api/findings", params=params).json()["items"]
    rows = _rows(client.get("/api/findings/export", params=params))
    assert [x["id"] for x in rows] == [f["id"] for f in listed] == [str(a["id"])]
    assert rows[0]["failed_rules"] == "R1 R7"
    assert (rows[0]["firm_name"], rows[0]["firm_registry_id"]) == (FIRM["name"], FIRM["registry_id"])


def test_export_prefixes_formulas(client, migrated_db):
    _findings(migrated_db.app_url, {"title": '=HYPERLINK("http://x")', "note": "-5% @home",
                                    "advertiser": {"name": "+48 600", "handle": "@x"}})
    row, = _rows(client.get("/api/findings/export"))
    assert row["title"] == "'=HYPERLINK(\"http://x\")"
    assert (row["note"], row["advertiser_name"], row["advertiser_handle"]) == ("'-5% @home", "'+48 600", "'@x")


@pytest.mark.parametrize("start", ["\t", "\r"])
def test_export_prefixes_tab_and_carriage_return(client, migrated_db, start):
    _findings(migrated_db.app_url, {"title": f"{start}=1+1"})
    assert _rows(client.get("/api/findings/export"))[0]["title"] == f"'{start}=1+1"


def test_export_keeps_polish_text(client, migrated_db):
    _findings(migrated_db.app_url, {"title": "Gwarantowany zysk – żółć"})
    assert _rows(client.get("/api/findings/export"))[0]["title"] == "Gwarantowany zysk – żółć"


def test_export_truncates(client, migrated_db, monkeypatch):
    import investwatch_api.routes.findings as routes

    monkeypatch.setattr(routes, "MAX_EXPORT_ROWS", 2)
    _findings(migrated_db.app_url, {}, {}, {})
    r = client.get("/api/findings/export")
    assert len(_rows(r)) == 2 and r.headers["x-total-count"] == "3" and r.headers["x-export-truncated"] == "true"


def test_export_of_nothing_is_a_header_row(client):
    r = client.get("/api/findings/export")
    assert r.status_code == 200 and _rows(r) == [] and r.headers["x-total-count"] == "0"


@pytest.mark.parametrize("params", [{"status": "archived"}, {"format": "pdf"}, {"module": "M4"},
                                    {"score_min": 2}, {"q": "a\x00b"}, {"sort": "title"}])
def test_export_invalid_params(client, params):
    r = client.get("/api/findings/export", params=params)
    assert r.status_code == 422 and r.json()["error"] == "validation_error"
