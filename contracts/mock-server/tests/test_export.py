"""GET /api/findings/{id}/export on the mock server (contract 1.2.0, issue #70)."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from conftest import assert_valid
from iw_mock_server.app import create_app
from iw_mock_server.settings import Settings
from openapi_check import assert_response_matches


@pytest.fixture
def client(contracts_dir):
    settings = Settings(contracts_dir=contracts_dir, replay_interval_s=0, scan_delay_s=0)
    with TestClient(create_app(settings)) as c:
        yield c


def _with_failed_rules(client) -> dict:
    items = client.get("/api/findings", params={"page_size": 200}).json()["items"]
    return next(f for f in items if any(r["result"] == "fail" for r in f["rules"]))


def test_every_mock_finding_exports_a_valid_pack(client):
    for item in client.get("/api/findings", params={"page_size": 200}).json()["items"]:
        r = client.get(f"/api/findings/{item['id']}/export")
        assert r.status_code == 200
        assert_response_matches("/findings/{id}/export", "get", r)
        body = r.json()
        assert_valid("finding", body["finding"])
        detail = client.get(f"/api/findings/{item['id']}").json()
        assert body["document"] == detail["document"] and body["screenshot_urls"] == detail["screenshot_urls"]
        assert body["finding"] == {k: v for k, v in detail.items() if k not in ("document", "screenshot_urls")}
        assert body["failed_rules"] == [r for r in detail["rules"] if r["result"] == "fail"]
        assert body["raw"]["available"] is False and body["raw"]["html"] is None
        expected = "not_found" if detail["document"].get("html_object_key") else "no_key"
        assert body["raw"]["unavailable_reason"] == expected


def test_html_page(client):
    f = _with_failed_rules(client)
    r = client.get(f"/api/findings/{f['id']}/export", params={"format": "html"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    assert r.headers["content-security-policy"].startswith("default-src 'none'")
    assert "script-src" not in r.headers["content-security-policy"]
    assert "Teczka sprawy" in r.text and "Naruszone reguły" in r.text and "<script" not in r.text


def test_unknown_finding_is_404(client):
    for fmt in ("json", "html"):
        r = client.get(f"/api/findings/{uuid.uuid4()}/export", params={"format": fmt})
        assert r.status_code == 404
        assert_response_matches("/findings/{id}/export", "get", r)


def test_bad_id_or_format_is_422(client):
    assert client.get("/api/findings/nope/export").status_code == 422
    f = _with_failed_rules(client)
    r = client.get(f"/api/findings/{f['id']}/export", params={"format": "pdf"})
    assert r.status_code == 422 and r.json()["details"][0]["loc"] == ["query", "format"]


def test_hostile_mock_text_is_escaped(client):
    f = _with_failed_rules(client)
    client.app.state.store.findings[f["id"]]["title"] = "<script>alert(1)</script>"
    page = client.get(f"/api/findings/{f['id']}/export", params={"format": "html"}).text
    assert "<script" not in page and "&lt;script&gt;alert(1)&lt;/script&gt;" in page
