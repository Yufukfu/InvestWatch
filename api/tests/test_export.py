"""GET /findings/{id}/export: the evidence pack, JSON and printable HTML (specs/rest-api, issue #70)."""

from __future__ import annotations

import hashlib
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert

from apiutil import FakeObjectStore, make_services
from conftest import assert_contract_valid
from dbutil import document_row, finding_row
from investwatch_api.app import create_app
from investwatch_api.db.tables import documents, findings
from investwatch_api.evidence import RAW_LIMIT
from openapi_check import assert_response_matches

RAW = "<html><body><h1>Zarabiaj 20%</h1></body></html>".encode()
RULES = [
    {"rule_id": "R1", "name": "Ostrzeżenie o ryzyku", "result": "fail", "severity": "high",
     "evidence": "Zarabiaj 20% rocznie.", "legal_basis": "art. 24 ust. 3 ustawy o obrocie instrumentami finansowymi",
     "explanation": "Brak ostrzeżenia.", "method": "rule"},
    {"rule_id": "R2", "name": "Wyniki historyczne", "result": "pass", "severity": "medium"},
    {"rule_id": "R3", "name": "Prognozy", "result": "fail", "severity": "low", "evidence": None},
    {"rule_id": "R4", "name": "Czcionka ostrzeżenia", "result": "uncertain", "severity": "medium"},
    {"rule_id": "R5", "name": "Dane podmiotu", "result": "not_applicable", "severity": "low"},
]
MODEL = {"pipeline_version": "0.3.0", "llm": "gemma-3-27b-it", "embedder": "bge-m3"}


def _insert(url, doc, finding):
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(insert(documents).values(doc))
        conn.execute(insert(findings).values(finding))
    engine.dispose()


@pytest.fixture
def objects():
    return FakeObjectStore({"html/doc.html": RAW})


def _case(url, **doc_over):
    doc_over.setdefault("html_object_key", "html/doc.html")
    doc_over.setdefault("payload", {"screenshots": {"desktop": "shot/d.png", "mobile": None}})
    doc = document_row(**doc_over)
    f = finding_row(doc["id"], rules=RULES, model=MODEL, score=0.9, summary="Reklama bez ostrzeżenia.")
    _insert(url, doc, f)
    return doc, f


def test_json_pack_holds_the_case_file(client, migrated_db, objects):
    doc, f = _case(migrated_db.app_url)
    r = client.get(f"/api/findings/{f['id']}/export")
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/json")
    assert_response_matches("/findings/{id}/export", "get", r)
    body = r.json()
    assert body["export_version"] == "1"
    assert body["finding"]["id"] == str(f["id"]) and body["finding"]["score"] == 0.9
    assert body["finding"]["model"] == MODEL and body["finding"]["risk_level"] == "high"
    assert_contract_valid("finding", body["finding"])
    assert body["document"]["url"] == doc["url"] and body["document"]["content_hash"] == doc["content_hash"]
    assert body["document"]["fetched_at"] and body["document"]["text"] == doc["text"]
    assert body["raw"] == {"object_key": "html/doc.html", "available": True, "unavailable_reason": None,
                           "sha256": hashlib.sha256(RAW).hexdigest(), "size_bytes": len(RAW), "truncated": False,
                           "html": RAW.decode()}
    assert body["screenshot_urls"] == {"desktop": f"/api/documents/{doc['id']}/screenshot/desktop"}
    assert [r["rule_id"] for r in body["failed_rules"]] == ["R1", "R3"]
    assert body["failed_rules"][0]["legal_basis"].startswith("art. 24")
    assert objects.requested == ["html/doc.html"]


def test_export_matches_the_detail(client, migrated_db):
    _, f = _case(migrated_db.app_url)
    detail = client.get(f"/api/findings/{f['id']}").json()
    body = client.get(f"/api/findings/{f['id']}/export").json()
    assert body["finding"] == {k: v for k, v in detail.items() if k not in ("document", "screenshot_urls")}
    assert body["document"] == detail["document"] and body["screenshot_urls"] == detail["screenshot_urls"]


def test_unknown_finding_is_404(client):
    for fmt in ("json", "html"):
        r = client.get(f"/api/findings/{uuid.uuid4()}/export?format={fmt}")
        assert r.status_code == 404 and "not found" in r.json()["error"]
        assert_response_matches("/findings/{id}/export", "get", r)


def test_malformed_id_and_format_are_422(client):
    assert client.get("/api/findings/not-a-uuid/export").status_code == 422
    r = client.get(f"/api/findings/{uuid.uuid4()}/export?format=pdf")
    assert r.status_code == 422 and r.json()["details"][0]["loc"] == ["query", "format"]


def test_no_raw_key(client, migrated_db, objects):
    _, f = _case(migrated_db.app_url, html_object_key=None)
    raw = client.get(f"/api/findings/{f['id']}/export").json()["raw"]
    assert raw["available"] is False and raw["unavailable_reason"] == "no_key" and raw["html"] is None
    assert objects.requested == []


def test_missing_raw_object(client, migrated_db):
    _, f = _case(migrated_db.app_url, html_object_key="html/gone.html")
    r = client.get(f"/api/findings/{f['id']}/export")
    assert_response_matches("/findings/{id}/export", "get", r)
    assert r.json()["raw"]["unavailable_reason"] == "not_found"


def test_store_down_degrades_only_the_raw_part(migrated_db, app_engine, redis_clean):
    _, f = _case(migrated_db.app_url)
    app = create_app(lambda: make_services(migrated_db.app_url, redis_clean, FakeObjectStore(up=False)))
    with TestClient(app) as c:
        r = c.get(f"/api/findings/{f['id']}/export")
    assert r.status_code == 200
    assert r.json()["raw"]["unavailable_reason"] == "store_down" and r.json()["finding"]["id"] == str(f["id"])


def test_large_raw_is_truncated_but_hashed_whole(migrated_db, app_engine, redis_clean):
    big = b"a" * (RAW_LIMIT + 10)
    _, f = _case(migrated_db.app_url, html_object_key="html/big.html")
    app = create_app(lambda: make_services(migrated_db.app_url, redis_clean, FakeObjectStore({"html/big.html": big})))
    with TestClient(app) as c:
        raw = c.get(f"/api/findings/{f['id']}/export").json()["raw"]
    assert raw["truncated"] is True and len(raw["html"]) == RAW_LIMIT
    assert raw["sha256"] == hashlib.sha256(big).hexdigest() and raw["size_bytes"] == len(big)


def test_html_page_is_printable_and_locked_down(client, migrated_db):
    doc, f = _case(migrated_db.app_url)
    r = client.get(f"/api/findings/{f['id']}/export?format=html")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    assert "script-src" not in r.headers["content-security-policy"]
    assert r.headers["content-security-policy"].startswith("default-src 'none'")
    assert r.headers["x-content-type-options"] == "nosniff"
    page = r.text
    for expected in (doc["url"], doc["content_hash"], "art. 24 ust. 3", "Zarabiaj 20% rocznie.",
                     f"/api/documents/{doc['id']}/screenshot/desktop", hashlib.sha256(RAW).hexdigest(),
                     "gemma-3-27b-it", "Naruszone reguły (2)"):
        assert expected in page, expected
    assert "&lt;h1&gt;Zarabiaj 20%&lt;/h1&gt;" in page and "<h1>Zarabiaj 20%</h1>" not in page


def test_html_escapes_scraped_and_model_text(client, migrated_db):
    evil = "<script>alert(1)</script>"
    rules = [{"rule_id": "R1", "name": evil, "result": "fail", "severity": "high", "evidence": evil,
              "legal_basis": '"><img src=x onerror=alert(1)>', "explanation": evil}]
    doc = document_row(text=f"Tekst {evil}", title=evil, url="https://alfa.example/?q=<b>",
                       canonical_url="javascript:alert(1)",
                       payload={"screenshots": {'x"><script>': "shot/x.png"}})
    f = finding_row(doc["id"], rules=rules, title=evil, summary=evil, note=evil)
    _insert(migrated_db.app_url, doc, f)
    page = client.get(f"/api/findings/{f['id']}/export?format=html").text
    assert "<script" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert 'href="javascript:' not in page and "javascript:alert(1)" in page  # shown as text, not a link
    assert "<img src=x" not in page
