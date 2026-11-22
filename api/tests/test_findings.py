"""Findings list, detail and PATCH (specs/rest-api)."""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import redis as redis_sync
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert, select

from apiutil import DEAD_REDIS, FakeObjectStore, make_services
from conftest import assert_contract_valid
from dbutil import document_row, finding_row, source_row
from investwatch_api.app import create_app
from investwatch_api.db.tables import documents, findings, job_errors, sources
from investwatch_api.thresholds import DEFAULTS, risk_level
from openapi_check import assert_response_matches, response_errors


def _insert(url, docs=(), finds=()):
    engine = create_engine(url)
    with engine.begin() as conn:
        for d in docs:
            conn.execute(insert(documents).values(d))
        for f in finds:
            conn.execute(insert(findings).values(f))
    engine.dispose()


def _many(url, n, **over):
    t = datetime.now(timezone.utc)
    docs = [document_row() for _ in range(n)]
    finds = [finding_row(d["id"], detected_at=t - timedelta(minutes=i), updated_at=t, **over)
             for i, d in enumerate(docs)]
    _insert(url, docs, finds)
    return finds


class Events:
    """Collects messages published on iw:events while the block runs."""

    def __init__(self, url):
        self._client = redis_sync.Redis.from_url(url)
        self._pubsub = self._client.pubsub()

    def __enter__(self):
        self._pubsub.subscribe("iw:events")
        self._pubsub.get_message(timeout=1)  # subscription confirmation
        return self

    def collect(self, wait=0.5) -> list[dict]:
        out, deadline = [], time.monotonic() + wait
        while time.monotonic() < deadline:
            msg = self._pubsub.get_message(timeout=0.1)
            if msg and msg["type"] == "message":
                out.append(json.loads(msg["data"]))
        return out

    def __exit__(self, *exc):
        self._pubsub.close()
        self._client.close()


# --- list ------------------------------------------------------------------------------------

def test_default_list_matches_the_contract(client, seeded):
    r = client.get("/api/findings")
    assert r.status_code == 200
    assert_response_matches("/findings", "get", r)
    body = r.json()
    assert body["total"] == len(seeded["findings"]) and body["page"] == 1 and body["page_size"] == 50
    times = [i["detected_at"] for i in body["items"]]
    assert times == sorted(times, reverse=True)
    for item in body["items"]:
        assert item["risk_level"] == risk_level(item["score"], DEFAULTS[item["module"]])


def test_combined_filters(client, seeded):
    r = client.get("/api/findings", params={"module": "M2", "status": "new,in_review", "platform": "web"})
    expected = [f for f in seeded["findings"]
                if f["module"] == "M2" and f["status"] in ("new", "in_review") and f["platform"] == "web"]
    assert r.json()["total"] == len(expected)
    assert {i["id"] for i in r.json()["items"]} == {f["id"] for f in expected}


def test_source_and_score_and_date_filters(client, seeded):
    doc_of = {d["id"]: d.get("source_id") for d in seeded["documents"]}
    src = next(s for s in doc_of.values() if s)
    by_source = client.get("/api/findings", params={"source_id": src}).json()
    assert {i["id"] for i in by_source["items"]} == {f["id"] for f in seeded["findings"]
                                                     if doc_of[f["document_id"]] == src}
    cut = sorted(f["score"] for f in seeded["findings"])[len(seeded["findings"]) // 2]
    assert all(i["score"] >= cut for i in client.get("/api/findings", params={"score_min": cut}).json()["items"])
    exact = seeded["findings"][0]["detected_at"]
    window = client.get("/api/findings", params={"date_from": exact, "date_to": exact}).json()
    assert {i["detected_at"] for i in window["items"]} == {exact}


def test_unknown_status_value(client):
    r = client.get("/api/findings", params={"status": "new,archived"})
    assert r.status_code == 422 and r.json()["details"][0]["loc"] == ["query", "status"]


def test_text_search_is_literal_and_covers_firm_and_advertiser(client, migrated_db):
    docs = [document_row() for _ in range(4)]
    _insert(migrated_db.app_url, docs, [
        finding_row(docs[0]["id"], title="Zysk 50% rocznie"),
        finding_row(docs[1]["id"], title="Zysk 500 zł"),
        finding_row(docs[2]["id"], title="x", firm={"name": "Alfa Inwestycje"}),
        finding_row(docs[3]["id"], title="y", advertiser={"name": "Jan", "handle": "@inwestor_jan"}),
    ])
    titles = lambda q: {i["title"] for i in client.get("/api/findings", params={"q": q}).json()["items"]}
    assert titles("50%") == {"Zysk 50% rocznie"}
    assert titles("ALFA") == {"x"}
    assert titles("@inwestor") == {"y"}
    assert titles("_") == {"y"}  # literal underscore in "@inwestor_jan"; as a wildcard it would match all four


def _two_on_one_document(url):
    """One document with an M1 and an M3 finding, plus a decoy document with an M3 finding."""
    doc, other = document_row(), document_row()
    m1 = finding_row(doc["id"], module="M1", score=0.88)
    m3 = finding_row(doc["id"], module="M3", score=0.84)
    _insert(url, [doc, other], [m1, m3, finding_row(other["id"], module="M3", score=0.9)])
    return doc["id"], m1, m3


def test_document_filter_returns_all_its_findings(client, migrated_db):
    doc, m1, m3 = _two_on_one_document(migrated_db.app_url)
    r = client.get("/api/findings", params={"document_id": str(doc)})
    assert r.status_code == 200
    assert_response_matches("/findings", "get", r)
    body = r.json()
    assert body["total"] == 2 and {i["id"] for i in body["items"]} == {str(m1["id"]), str(m3["id"])}


def test_document_filter_combines_with_module(client, migrated_db):
    doc, _, m3 = _two_on_one_document(migrated_db.app_url)
    body = client.get("/api/findings", params={"document_id": str(doc), "module": "M3"}).json()
    assert body["total"] == 1 and [i["id"] for i in body["items"]] == [str(m3["id"])]


def test_document_filter_combines_with_sort_and_pagination(client, migrated_db):
    doc, m1, _ = _two_on_one_document(migrated_db.app_url)
    body = client.get("/api/findings", params={"document_id": str(doc), "sort": "score",
                                               "page": 2, "page_size": 1}).json()
    assert body["total"] == 2 and body["page"] == 2 and body["page_size"] == 1
    assert [i["id"] for i in body["items"]] == [str(m1["id"])]  # 0.84 then 0.88


def test_document_filter_unknown_and_malformed(client, migrated_db):
    _two_on_one_document(migrated_db.app_url)
    empty = client.get("/api/findings", params={"document_id": str(uuid.uuid4())})
    assert empty.status_code == 200 and empty.json()["items"] == [] and empty.json()["total"] == 0
    bad = client.get("/api/findings", params={"document_id": "not-a-uuid"})
    assert bad.status_code == 422 and bad.json()["details"][0]["loc"] == ["query", "document_id"]


def test_page_past_the_end(client, migrated_db):
    _many(migrated_db.app_url, 60)
    body = client.get("/api/findings", params={"page": 3, "page_size": 50}).json()
    assert body == {"items": [], "total": 60, "page": 3, "page_size": 50}
    assert len(client.get("/api/findings", params={"page": 2}).json()["items"]) == 10


@pytest.mark.parametrize("params", [{"page_size": 201}, {"page": 0}, {"sort": "title"}, {"score_min": 1.5}])
def test_paging_and_sort_limits(client, params):
    assert client.get("/api/findings", params=params).status_code == 422


def test_sort_by_score(client, seeded):
    items = client.get("/api/findings", params={"sort": "-score"}).json()["items"]
    assert [i["score"] for i in items] == sorted((f["score"] for f in seeded["findings"]), reverse=True)


def test_risk_filter_uses_the_same_rule(client, migrated_db):
    # the rule, not the defaults (ADR 0316 moved M2's default): pin M2 at 0.5
    client.put("/api/settings/thresholds", json={"M1": 0.6, "M2": 0.5, "M3": 0.7})
    docs = [document_row() for _ in range(4)]
    _insert(migrated_db.app_url, docs, [finding_row(d["id"], module="M2", score=s)
                                        for d, s in zip(docs, (0.5, 0.49, 0.3, 0.29))])
    levels = {i["score"]: i["risk_level"] for i in client.get("/api/findings").json()["items"]}
    assert levels == {0.5: "high", 0.49: "medium", 0.3: "medium", 0.29: "low"}
    medium = client.get("/api/findings", params={"risk_level": "medium"}).json()
    assert medium["total"] == 2 and {i["score"] for i in medium["items"]} == {0.49, 0.3}


def test_threshold_change_applies_at_once(client, migrated_db):
    doc = document_row()
    f = finding_row(doc["id"], module="M2", score=0.6)
    _insert(migrated_db.app_url, [doc], [f])
    assert client.get(f"/api/findings/{f['id']}").json()["risk_level"] == "high"
    client.put("/api/settings/thresholds", json={"M1": 0.6, "M2": 0.7, "M3": 0.7})
    assert client.get(f"/api/findings/{f['id']}").json()["risk_level"] == "medium"


def test_redis_unavailable_uses_defaults(migrated_db, app_engine):
    doc = document_row()
    f = finding_row(doc["id"], module="M2", score=0.5)
    _insert(migrated_db.app_url, [doc], [f])
    with TestClient(create_app(lambda: make_services(migrated_db.app_url, DEAD_REDIS, FakeObjectStore()))) as c:
        r = c.get("/api/findings")
        assert r.status_code == 200 and r.json()["items"][0]["risk_level"] == "high"
        assert c.get("/api/health").json()["services"]["redis"] == "down"


# --- detail ----------------------------------------------------------------------------------

def _detail_parts_valid(body):
    """Open question 1 (follow-ups): the finding and document parts are validated separately."""
    finding = {k: v for k, v in body.items() if k not in ("document", "screenshot_urls")}
    assert_contract_valid("finding", finding)
    if body["document"] is not None:
        assert_contract_valid("scraped-document", body["document"])


def test_document_with_two_screenshots(client, migrated_db):
    doc = document_row(payload={"screenshots": {"desktop": "shot/a/desktop.png", "tablet": None,
                                                "mobile": "shot/a/mobile.png"}})
    f = finding_row(doc["id"])
    _insert(migrated_db.app_url, [doc], [f])
    body = client.get(f"/api/findings/{f['id']}").json()
    assert body["screenshot_urls"] == {vp: f"/api/documents/{doc['id']}/screenshot/{vp}" for vp in ("desktop", "mobile")}
    assert body["document"]["id"] == str(doc["id"])
    _detail_parts_valid(body)


def test_document_without_screenshots(client, migrated_db):
    doc = document_row()
    f = finding_row(doc["id"])
    _insert(migrated_db.app_url, [doc], [f])
    body = client.get(f"/api/findings/{f['id']}").json()
    assert body["screenshot_urls"] == {} and body["document"]["text"] == doc["text"]
    _detail_parts_valid(body)


def test_every_mock_detail_is_valid(client, seeded):
    for f in seeded["findings"]:
        _detail_parts_valid(client.get(f"/api/findings/{f['id']}").json())


def test_unknown_finding(client):
    missing = uuid.uuid4()
    for r in (client.get(f"/api/findings/{missing}"), client.patch(f"/api/findings/{missing}", json={"note": "x"})):
        assert r.status_code == 404 and set(r.json()) == {"error"}
        assert not response_errors("/findings/{id}", "get", 404, r.json())


def test_malformed_path_id(client):
    r = client.get("/api/findings/not-a-uuid")
    assert r.status_code == 422 and r.json()["error"] == "validation_error" and r.json()["details"]


# --- PATCH -----------------------------------------------------------------------------------

def _one(migrated_db, **over):
    doc = document_row()
    f = finding_row(doc["id"], **over)
    _insert(migrated_db.app_url, [doc], [f])
    return f


def _stored(migrated_db, finding_id):
    engine = create_engine(migrated_db.app_url)
    with engine.connect() as conn:
        row = conn.execute(select(findings).where(findings.c.id == finding_id)).mappings().one()
    engine.dispose()
    return row


def test_status_change(client, migrated_db, redis_clean):
    f = _one(migrated_db)
    with Events(redis_clean) as events:
        r = client.patch(f"/api/findings/{f['id']}", json={"status": "confirmed"})
        got = events.collect()
    assert r.status_code == 200 and r.json()["status"] == "confirmed"
    assert_response_matches("/findings/{id}", "patch", r)
    from investwatch_api.db.mapping import parse_time

    assert parse_time(r.json()["updated_at"]) > f["updated_at"]
    assert _stored(migrated_db, f["id"])["updated_at"] > f["updated_at"]
    assert _stored(migrated_db, f["id"])["status"] == "confirmed"
    assert [(e["type"], e["data"]) for e in got] == [("finding.updated", {"id": str(f["id"]), "status": "confirmed"})]
    assert_contract_valid("events", got[0])


def test_note_only(client, migrated_db, redis_clean):
    f = _one(migrated_db, status="in_review")
    with Events(redis_clean) as events:
        r = client.patch(f"/api/findings/{f['id']}", json={"note": "sprawdzone"})
        got = events.collect()
    assert r.json()["note"] == "sprawdzone" and r.json()["status"] == "in_review"
    assert [e["data"] for e in got] == [{"id": str(f["id"]), "status": "in_review"}]


def test_clearing_a_note(client, migrated_db):
    f = _one(migrated_db, note="stara")
    assert "note" not in client.patch(f"/api/findings/{f['id']}", json={"note": None}).json()
    assert _stored(migrated_db, f["id"])["note"] is None


@pytest.mark.parametrize("body", [{}, {"status": None}, {"status": "archived"}, {"score": 1},
                                  {"note": "a\x00b"}, {"note": "x" * 10_001}],
                         ids=["empty", "null-status", "bad-status", "extra-key", "nul-note", "long-note"])
def test_invalid_bodies(client, migrated_db, redis_clean, body):
    f = _one(migrated_db)
    with Events(redis_clean) as events:
        r = client.patch(f"/api/findings/{f['id']}", json=body)
        got = events.collect(0.3)
    assert r.status_code == 422 and r.json()["error"] == "validation_error"
    assert _stored(migrated_db, f["id"])["status"] == "new" and got == []


def test_redis_down_after_commit(migrated_db, app_engine, caplog):
    f = _one(migrated_db)
    with TestClient(create_app(lambda: make_services(migrated_db.app_url, DEAD_REDIS, FakeObjectStore()))) as c:
        r = c.patch(f"/api/findings/{f['id']}", json={"status": "closed"})
    assert r.status_code == 200 and r.json()["status"] == "closed"
    assert _stored(migrated_db, f["id"])["status"] == "closed"
    assert any(rec.levelname == "ERROR" and "publish" in rec.getMessage() for rec in caplog.records)


@pytest.mark.parametrize("params", [{"page": 10**12}, {"q": "a\x00b"}, {"q": "x" * 201}, {"platform": "web\x00"}])
def test_hostile_query_values_are_422_not_500(client, params):
    r = client.get("/api/findings", params=params)
    assert r.status_code == 422 and r.json()["error"] == "validation_error"


def test_database_down_gives_the_error_shape(redis_clean):
    from apiutil import DEAD_PG

    app = create_app(lambda: make_services(DEAD_PG, redis_clean, FakeObjectStore()))
    with TestClient(app, raise_server_exceptions=False) as c:
        r = c.get("/api/findings")
    assert r.status_code == 500 and r.json() == {"error": "internal error"}


@pytest.mark.parametrize("raw", ["", ",", " , "])
def test_empty_status_list(client, raw):
    r = client.get("/api/findings", params={"status": raw})
    assert r.status_code == 422 and r.json()["details"][0]["loc"] == ["query", "status"]


def test_longest_note_is_accepted(client, migrated_db):
    f = _one(migrated_db)
    assert client.patch(f"/api/findings/{f['id']}", json={"note": "x" * 10_000}).status_code == 200


# --- re-scan state (issue #71): document.scrape_meta.rescan --------------------------------------

def _rescan(client, finding):
    body = client.get(f"/api/findings/{finding['id']}").json()
    _detail_parts_valid(body)
    return body["document"]["scrape_meta"]["rescan"]


def _job_error(url, **over):
    row = dict(id=uuid.uuid4(), source_id=None, url="https://alfa.example/oferta", reason="http_error",
               detail="HTTP 404", occurred_at=datetime.now(timezone.utc))
    row.update(over)
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(insert(job_errors).values(row))
    engine.dispose()


def _rescanned(migrated_db, **newer_over):
    """An old document with a finding and a later fetch of the same page."""
    src = source_row()
    t = datetime.now(timezone.utc) - timedelta(hours=2)
    old = document_row(source_id=src["id"], fetched_at=t, payload={"scrape_meta": {"scraper": "httpx"}})
    new = document_row(source_id=src["id"], fetched_at=t + timedelta(hours=1), **newer_over)
    f_old, f_new = finding_row(old["id"]), finding_row(new["id"])
    engine = create_engine(migrated_db.app_url)
    with engine.begin() as conn:
        conn.execute(insert(sources).values(src))
    engine.dispose()
    _insert(migrated_db.app_url, [old, new], [f_old, f_new])
    return src, old, new, f_old, f_new


def test_rescan_state_current_without_a_later_fetch(client, migrated_db):
    doc = document_row()
    f = finding_row(doc["id"])
    _insert(migrated_db.app_url, [doc], [f])
    state = _rescan(client, f)
    assert state["state"] == "current" and state["latest_document_id"] is None
    assert datetime.fromisoformat(state["checked_at"]) == doc["fetched_at"]


def test_rescan_with_new_text_marks_the_old_finding_changed(client, migrated_db):
    _, old, new, f_old, f_new = _rescanned(migrated_db)
    state = _rescan(client, f_old)
    assert state["state"] == "changed" and state["latest_document_id"] == str(new["id"])
    assert _rescan(client, f_new)["state"] == "current"
    meta = client.get(f"/api/findings/{f_old['id']}").json()["document"]["scrape_meta"]
    assert meta["scraper"] == "httpx"  # the scraper's own keys are kept


def test_rescan_with_gone_status_marks_removed(client, migrated_db):
    for status in (404, 410):
        _, _, new, f_old, _ = _rescanned(migrated_db, http_status=status)
        state = _rescan(client, f_old)
        assert state["state"] == "removed" and state["latest_document_id"] == str(new["id"])


def test_rescan_same_url_other_source_or_other_page_is_not_a_change(client, migrated_db):
    _, old, _, f_old, _ = _rescanned(migrated_db, url="https://alfa.example/inna")
    assert _rescan(client, f_old)["state"] == "current"
    other = source_row()
    engine = create_engine(migrated_db.app_url)
    with engine.begin() as conn:
        conn.execute(insert(sources).values(other))
    engine.dispose()
    later = document_row(source_id=other["id"], fetched_at=old["fetched_at"] + timedelta(minutes=5))
    _insert(migrated_db.app_url, [later])
    assert _rescan(client, f_old)["state"] == "current"


def test_rescan_matches_the_canonical_url(client, migrated_db):
    _, _, new, f_old, _ = _rescanned(migrated_db, url="https://alfa.example/oferta?utm_source=x",
                                     canonical_url="https://alfa.example/oferta")
    assert _rescan(client, f_old)["latest_document_id"] == str(new["id"])


def test_rescan_gone_job_error_after_the_last_fetch_marks_removed(client, migrated_db):
    src, old, new, f_old, f_new = _rescanned(migrated_db)
    _job_error(migrated_db.app_url, source_id=src["id"], occurred_at=new["fetched_at"] + timedelta(minutes=1))
    for f in (f_old, f_new):
        state = _rescan(client, f)
        assert state["state"] == "removed" and state["latest_document_id"] is None


def test_rescan_job_error_before_the_last_fetch_or_not_gone_is_ignored(client, migrated_db):
    src, old, new, f_old, f_new = _rescanned(migrated_db)
    _job_error(migrated_db.app_url, source_id=src["id"], occurred_at=old["fetched_at"] + timedelta(minutes=1))
    _job_error(migrated_db.app_url, source_id=src["id"], detail="HTTP 500",
               occurred_at=new["fetched_at"] + timedelta(minutes=1))
    _job_error(migrated_db.app_url, source_id=None, occurred_at=new["fetched_at"] + timedelta(minutes=1))
    assert _rescan(client, f_old)["state"] == "changed"
    assert _rescan(client, f_new)["state"] == "current"
