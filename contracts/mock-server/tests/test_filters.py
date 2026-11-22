from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from iw_mock_server.app import create_app
from iw_mock_server.settings import Settings
from iw_mock_server.store import Store, load_mock_data


@pytest.fixture
def store(contracts_dir):
    return Store(load_mock_data(contracts_dir))


@pytest.fixture
def client(contracts_dir, store):
    settings = Settings(contracts_dir=contracts_dir, replay_interval_s=0, scan_delay_s=0)
    with TestClient(create_app(settings, store)) as c:
        yield c


def items(client, query: str) -> list[dict]:
    r = client.get(f"/api/findings?{query}")
    assert r.status_code == 200, r.text
    return r.json()["items"]


def test_filter_by_module_and_status_list(client, store):
    expected = [f for f in store.findings.values() if f["module"] == "M2" and f["status"] in ("new", "in_review")]

    r = client.get("/api/findings?module=M2&status=new,in_review").json()

    assert {i["id"] for i in r["items"]} == {f["id"] for f in expected}
    assert r["total"] == len(expected) > 0


def test_filter_by_platform(client):
    result = items(client, "platform=instagram")

    assert result and all(i["platform"] == "instagram" for i in result)


def test_filter_by_source_id_uses_the_document_source(client, store):
    source_id = next(d["source_id"] for d in store.documents.values() if d["source_id"])
    doc_ids = {d["id"] for d in store.documents.values() if d["source_id"] == source_id}

    result = items(client, f"source_id={source_id}")

    assert result and {i["document_id"] for i in result} <= doc_ids


def test_filter_by_risk_level_and_score_min(client):
    high = items(client, "risk_level=high")
    above = items(client, "score_min=0.8")

    assert high and all(i["risk_level"] == "high" for i in high)
    assert above and all(i["score"] >= 0.8 for i in above)


def test_filter_by_date_range(client, store):
    times = sorted(f["detected_at"] for f in store.findings.values())
    lo, hi = times[2], times[5]

    result = items(client, f"date_from={lo}&date_to={hi}")

    assert result and all(lo <= i["detected_at"] <= hi for i in result)
    assert len(result) == 4


def test_full_text_search_is_case_insensitive(client):
    result = items(client, "q=INWESTOR_JAN")

    assert len(result) == 1
    assert result[0]["advertiser"]["handle"] == "@inwestor_jan"


def test_search_does_not_look_into_the_summary(client, store):
    word = "eksponuje"  # appears only in a summary, not in title, excerpt, firm or advertiser
    assert any(word in (f.get("summary") or "") for f in store.findings.values())

    assert items(client, f"q={word}") == []


def test_search_matches_firm_name(client, store):
    # "Dom Maklerski" appears only in the firm name, never in a title, excerpt or advertiser
    expected = {f["id"] for f in store.findings.values()
                if "Alfa Inwestycje Dom Maklerski" in (f["firm"] or {}).get("name", "")}

    result = items(client, "q=alfa inwestycje dom maklerski")

    assert expected and {i["id"] for i in result} == expected


@pytest.mark.parametrize("sort", ["score", "-score", "detected_at", "-detected_at"])
def test_sort(client, sort):
    key = sort.lstrip("-")
    result = items(client, f"sort={sort}")

    values = [i[key] for i in result]
    assert values == sorted(values, reverse=sort.startswith("-"))


def test_default_sort_is_newest_first(client):
    values = [i["detected_at"] for i in items(client, "")]

    assert values == sorted(values, reverse=True)


def test_pagination_returns_the_right_slice(client):
    everything = items(client, "page_size=200")

    r = client.get("/api/findings?page=2&page_size=2").json()

    assert r["page"] == 2 and r["page_size"] == 2 and r["total"] == len(everything)
    assert [i["id"] for i in r["items"]] == [i["id"] for i in everything[2:4]]


def test_no_matches_returns_empty_list(client):
    r = client.get("/api/findings?q=nothing-matches-this").json()

    assert r["items"] == [] and r["total"] == 0


@pytest.mark.parametrize(
    "query",
    ["module=M9", "page_size=0", "page_size=201", "page=0", "status=approved", "risk_level=extreme",
     "score_min=1.5", "sort=title", "source_id=not-a-uuid", "document_id=not-a-uuid", "date_from=yesterday"],
)
def test_invalid_filter_values_are_422(client, query):
    r = client.get(f"/api/findings?{query}")

    assert r.status_code == 422
    assert "error" in r.json()


@pytest.mark.parametrize("query", ["status=,", "status=", "status=%20"])
def test_blank_status_filter_is_422(client, query):
    # an empty set would silently drop the filter and return every finding
    assert client.get(f"/api/findings?{query}").status_code == 422


@pytest.mark.parametrize("sort", ["score", "-score", "detected_at", "-detected_at"])
def test_sort_ties_are_broken_by_id(client, store, sort):
    # a SQL ORDER BY in the real api/ does not keep insertion order, so the mock must not rely on it
    for f in store.findings.values():
        f.update(score=0.5, detected_at="2026-11-21T10:00:00Z")
    store.findings = dict(reversed(list(store.findings.items())))

    result = items(client, f"sort={sort}&page_size=200")

    assert [i["id"] for i in result] == sorted(store.findings)


def _shared_document(store) -> str:
    seen: dict[str, int] = {}
    for f in store.findings.values():
        seen[f["document_id"]] = seen.get(f["document_id"], 0) + 1
    return next(doc for doc, n in seen.items() if n > 1)


def test_filter_by_document_returns_all_its_findings(client, store):
    doc = _shared_document(store)

    r = client.get(f"/api/findings?document_id={doc}").json()

    assert r["total"] == 2
    assert {i["document_id"] for i in r["items"]} == {doc}
    assert sorted(i["module"] for i in r["items"]) == ["M1", "M3"]


def test_filter_by_document_combines_with_module(client, store):
    doc = _shared_document(store)

    r = client.get(f"/api/findings?document_id={doc}&module=M3").json()

    assert r["total"] == 1 and [(i["document_id"], i["module"]) for i in r["items"]] == [(doc, "M3")]


def test_filter_by_document_combines_with_sort_and_pagination(client, store):
    doc = _shared_document(store)
    by_score = sorted((f for f in store.findings.values() if f["document_id"] == doc), key=lambda f: f["score"])

    r = client.get(f"/api/findings?document_id={doc}&sort=score&page=2&page_size=1").json()

    assert r["total"] == 2 and r["page"] == 2 and r["page_size"] == 1
    assert [i["id"] for i in r["items"]] == [by_score[1]["id"]]


def test_filter_by_unknown_document_is_empty(client):
    r = client.get("/api/findings?document_id=00000000-0000-4000-8000-000000000000")

    assert r.status_code == 200 and r.json()["items"] == [] and r.json()["total"] == 0
