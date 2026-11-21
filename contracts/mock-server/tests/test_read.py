from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from conftest import assert_valid
from iw_mock_server.app import create_app
from iw_mock_server.settings import Settings
from iw_mock_server.store import Store, load_mock_data
from openapi_check import assert_response_matches, response_errors


@pytest.fixture
def client(contracts_dir):
    settings = Settings(contracts_dir=contracts_dir, replay_interval_s=0, scan_delay_s=0)
    with TestClient(create_app(settings)) as c:
        yield c


def first_finding_id(client) -> str:
    return client.get("/api/findings").json()["items"][0]["id"]


def test_openapi_check_rejects_a_wrong_body():
    bad = {"items": [{"id": "x", "module": "M9"}], "total": 1, "page": 1, "page_size": 50}

    assert response_errors("/findings", "get", 200, bad)
    assert response_errors("/settings/thresholds", "get", 200, {"M1": 2})


def test_list_findings_matches_contract(client):
    r = client.get("/api/findings")

    assert r.status_code == 200
    assert_response_matches("/findings", "get", r)
    body = r.json()
    assert body["total"] == 9 and body["page"] == 1 and len(body["items"]) == 9
    assert all(item["risk_level"] in {"high", "medium", "low"} for item in body["items"])


def test_finding_detail_has_document_and_screenshot_urls(client):
    fid = first_finding_id(client)

    r = client.get(f"/api/findings/{fid}")

    assert r.status_code == 200
    detail = r.json()
    document = detail.pop("document")
    screenshot_urls = detail.pop("screenshot_urls")
    assert_valid("finding", detail)
    assert_valid("scraped-document", document)
    assert detail["document_id"] == document["id"]
    assert isinstance(screenshot_urls, dict)


def test_detail_of_document_with_screenshots_lists_their_urls(client):
    items = client.get("/api/findings?module=M2").json()["items"]
    with_shots = next(i for i in items if i["title"].startswith("Obietnica 18%"))

    urls = client.get(f"/api/findings/{with_shots['id']}").json()["screenshot_urls"]

    assert set(urls) == {"desktop", "tablet", "mobile"}
    assert urls["desktop"] == f"/api/documents/{with_shots['document_id']}/screenshot/desktop"


def test_unknown_finding_is_404_with_error_body(client):
    r = client.get(f"/api/findings/{uuid.uuid4()}")

    assert r.status_code == 404
    assert_response_matches("/findings/{id}", "get", r)


def test_malformed_finding_id_is_422(client):
    r = client.get("/api/findings/not-a-uuid")

    assert r.status_code == 422
    assert "error" in r.json() and r.json()["details"]


def test_trend_module_filter_zeroes_other_modules(client):
    points = client.get("/api/stats/trend?module=M2").json()["points"]

    assert sum(p["M2"] for p in points) > 0
    assert all(p["M1"] == 0 and p["M3"] == 0 for p in points)


def test_trend_risk_level_counts_only_findings_of_that_level(client):
    expected = len(client.get("/api/findings?risk_level=high&page_size=200").json()["items"])

    points = client.get("/api/stats/trend?risk_level=high").json()["points"]

    assert sum(p["M1"] + p["M2"] + p["M3"] for p in points) == expected


def test_trend_date_range(client):
    points = client.get("/api/stats/trend").json()["points"]
    lo, hi = points[3]["t"], points[10]["t"]

    subset = client.get(f"/api/stats/trend?date_from={lo}&date_to={hi}").json()["points"]

    assert [p["t"] for p in subset] == [p["t"] for p in points[3:11]]


@pytest.mark.parametrize(
    ("url", "path"),
    [
        ("/api/stats/summary", "/stats/summary"),
        ("/api/stats/trend", "/stats/trend"),
        ("/api/stats/trend?bucket=day", "/stats/trend"),
        ("/api/calibration?module=M2", "/calibration"),
        ("/api/settings/thresholds", "/settings/thresholds"),
        ("/api/sources", "/sources"),
        ("/api/health", "/health"),
    ],
)
def test_read_endpoints_match_contract(client, url, path):
    r = client.get(url)

    assert r.status_code == 200
    assert_response_matches(path, "get", r)


def test_summary_counts_match_findings(client):
    body = client.get("/api/stats/summary").json()

    assert body["total"] == 9
    assert sum(body["by_module"].values()) == 9
    assert sum(body["by_status"].values()) == 9
    assert sum(body["by_risk_level"].values()) == 9


def test_trend_by_day_aggregates_hourly_points(client):
    hourly = client.get("/api/stats/trend?bucket=hour").json()["points"]
    daily = client.get("/api/stats/trend?bucket=day").json()

    assert daily["bucket"] == "day"
    for module in ("M1", "M2", "M3"):
        assert sum(p[module] for p in daily["points"]) == sum(p[module] for p in hourly)


def test_calibration_uses_current_threshold(contracts_dir):
    store = Store(load_mock_data(contracts_dir))
    store.thresholds["M3"] = 0.42
    settings = Settings(contracts_dir=contracts_dir, replay_interval_s=0)
    with TestClient(create_app(settings, store)) as c:
        body = c.get("/api/calibration?module=M3").json()

    assert body["module"] == "M3"
    assert body["current_threshold"] == 0.42


def test_calibration_without_module_is_422(client):
    assert client.get("/api/calibration").status_code == 422


def test_screenshot_placeholder_is_png(client):
    items = client.get("/api/findings?module=M2").json()["items"]
    doc_id = next(i for i in items if i["title"].startswith("Obietnica 18%"))["document_id"]

    r = client.get(f"/api/documents/{doc_id}/screenshot/desktop")

    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert r.content.startswith(b"\x89PNG\r\n\x1a\n")


def test_screenshot_missing_is_404(client):
    items = client.get("/api/findings?platform=instagram").json()["items"]
    doc_without_shots = items[0]["document_id"]

    assert client.get(f"/api/documents/{doc_without_shots}/screenshot/desktop").status_code == 404
    assert client.get(f"/api/documents/{uuid.uuid4()}/screenshot/desktop").status_code == 404


def test_cors_header_for_allowed_origin(client):
    r = client.get("/api/findings", headers={"Origin": "http://localhost:5173"})

    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_no_cors_header_for_other_origin(client):
    r = client.get("/api/findings", headers={"Origin": "http://evil.example"})

    assert "access-control-allow-origin" not in r.headers
