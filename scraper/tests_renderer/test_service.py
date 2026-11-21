import base64
import logging

import pytest
from aiohttp.test_utils import TestClient, TestServer

from iw_renderer.render import Renderer
from iw_renderer.service import MAX_BODY_BYTES, create_app
from iw_renderer.settings import RenderLimits

PNG = b"\x89PNG\r\n\x1a\n"
CHROME = {
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
    "accept-language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
}


@pytest.fixture
async def client(browser, address_check):
    app = create_app(Renderer(browser, address_check, RenderLimits(timeout_seconds=30)))
    async with TestClient(TestServer(app)) as test_client:
        yield test_client


def body_for(server, path="/", **extra):
    return {
        "url": f"http://source.test:{server.port}{path}",
        "source_host": "source.test",
        "viewport": "desktop",
        "headers": CHROME,
        "ports": [server.port],
        **extra,
    }


async def test_a_render_returns_the_png_and_the_render_meta(server, client):
    server.serve("source.test", "/", "<p>x</p>")

    response = await client.post("/render", json=body_for(server))
    payload = await response.json()

    assert response.status == 200
    assert base64.b64decode(payload["png_base64"]).startswith(PNG)
    assert payload["viewport"] == "desktop" and payload["status"] == 200
    assert payload["truncated"] is False and payload["browser_version"].split(".")[0].isdigit()
    assert payload["final_url"].startswith("http://source.test:")


async def test_a_block_is_answered_403_with_its_retry_after(server, client):
    server.routes[("source.test", "/")] = (429, {"Retry-After": "120"}, b"slow down")

    response = await client.post("/render", json=body_for(server))
    payload = await response.json()

    assert response.status == 403
    assert payload == {"error": {"kind": "blocked", "detail": "HTTP 429", "retry_after": "120"}}


async def test_a_redirect_to_another_site_is_answered_422_refused(server, client):
    server.routes[("source.test", "/")] = (302, {"Location": f"http://other.test:{server.port}/"}, b"")
    server.serve("other.test", "/", "elsewhere")

    response = await client.post("/render", json=body_for(server))
    payload = await response.json()

    assert response.status == 422
    assert payload["error"]["kind"] == "refused" and "navigation away" in payload["error"]["detail"]


async def test_another_failure_is_answered_502(server, client):
    server.routes[("source.test", "/")] = (500, {}, b"oops")

    response = await client.post("/render", json=body_for(server))

    assert response.status == 502
    assert (await response.json())["error"] == {"kind": "failed", "detail": "HTTP 500"}


@pytest.mark.parametrize(
    "change",
    [
        {"viewport": "watch"},
        {"url": "file:///etc/passwd"},
        {"url": "http://source.test:80/" + "a" * 3000},
        {"url": "http://user:pw@source.test/"},
        {"headers": {"accept-language": "pl"}},
        {"headers": {"user-agent": "x\r\nX-Injected: 1"}},
        {"ports": [True]},
        {"proxy": "ftp://proxy.test:21"},
        {"source_host": ""},
        {"source_host": "source.test/evil"},
        {"source_host": "user@source.test"},
        {"source_host": "other.test"},
        {"headers": {"user-agent": 5}},
        {"headers": {}},
        {"headers": {**CHROME, **{f"h{i}": "v" for i in range(60)}}},
        {"proxy": 7},
        {"ports": []},
        {"ports": [0]},
        {"ports": list(range(1, 30))},
        {"timeout_seconds": 0},
        {"timeout_seconds": "soon"},
        {"timeout_seconds": 100000},
    ],
    ids=lambda c: next(iter(c)) + "=" + repr(next(iter(c.values())))[:20],
)
async def test_an_invalid_request_is_refused_before_any_navigation(server, client, change):
    server.serve("source.test", "/", "<p>x</p>")

    response = await client.post("/render", json={**body_for(server), **change})

    assert response.status == 400
    assert (await response.json())["error"]["kind"] == "invalid_request"
    assert server.requests == []


@pytest.mark.parametrize("missing", ["url", "source_host", "viewport", "headers", "ports"])
async def test_a_missing_field_is_refused(server, client, missing):
    body = body_for(server)
    del body[missing]

    response = await client.post("/render", json=body)

    assert response.status == 400 and missing in (await response.json())["error"]["detail"]


async def test_a_body_that_is_not_json_or_not_an_object_is_refused(client):
    for data in (b"{not json", b"[1, 2]", b""):
        response = await client.post("/render", data=data, headers={"Content-Type": "application/json"})
        assert response.status == 400


async def test_a_body_over_the_size_limit_is_refused(server, client):
    response = await client.post("/render", json=body_for(server, proxy="x" * (MAX_BODY_BYTES + 1)))

    assert response.status == 413


async def test_the_proxy_and_the_query_never_reach_the_logs_or_the_answer(server, client, caplog):
    server.routes[("source.test", "/page")] = (500, {}, b"oops")
    caplog.set_level(logging.DEBUG)

    response = await client.post(
        "/render", json=body_for(server, path="/page?token=SECRETQ", proxy="http://user:SECRETPW@127.0.0.1:1")
    )

    everything = caplog.text + await response.text()
    assert "SECRETQ" not in everything and "SECRETPW" not in everything and "127.0.0.1:1" not in everything


async def test_health_reports_the_browser_version(client):
    response = await client.get("/health")
    payload = await response.json()

    assert response.status == 200
    assert payload["status"] == "ok" and payload["browser_version"].split(".")[0].isdigit()


async def test_health_is_503_when_the_browser_is_gone(browser, address_check, server):
    await browser.close()
    app = create_app(Renderer(browser, address_check))
    async with TestClient(TestServer(app)) as dead:
        response = await dead.get("/health")
        payload = await response.json()

    assert response.status == 503 and payload == {"status": "unhealthy"}


async def test_header_names_are_case_insensitive(server, client):
    server.serve("source.test", "/", "<p>x</p>")
    headers = {"User-Agent": CHROME["user-agent"], "Accept-Language": CHROME["accept-language"]}

    response = await client.post("/render", json=body_for(server, headers=headers))

    assert response.status == 200
