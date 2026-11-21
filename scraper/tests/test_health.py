import asyncio
import json

import pytest

from iw_scraper.health import check_redis, serve_health


async def get(server: asyncio.Server, path: str = "/health", method: str = "GET"):
    port = server.sockets[0].getsockname()[1]
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(f"{method} {path} HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n".encode())
    await writer.drain()
    raw = await asyncio.wait_for(reader.read(), 5)
    writer.close()
    head, _, body = raw.partition(b"\r\n\r\n")
    return int(head.split()[1]), body


async def ok():
    return None


def failing(message):
    async def check():
        raise ConnectionError(message)

    return check


@pytest.fixture
async def serve():
    servers = []

    async def start(checks, **kwargs):
        kwargs.setdefault("cache_ttl", 0.0)  # these tests change a dependency between requests
        server = await serve_health(checks, host="127.0.0.1", port=0, **kwargs)
        servers.append(server)
        return server

    yield start
    for server in servers:
        server.close()
        await server.wait_closed()


async def test_health_is_200_when_every_dependency_answers(serve):
    server = await serve({"postgres": ok, "redis": ok, "minio": ok})

    status, body = await get(server)

    assert (status, json.loads(body)) == (200, {"status": "ok"})


async def test_health_is_503_and_names_every_failing_dependency(serve):
    server = await serve({"postgres": failing("db down"), "redis": ok, "minio": failing("no route")})

    status, body = await get(server)

    assert status == 503
    assert json.loads(body) == {"status": "unavailable", "failing": ["minio", "postgres"]}


async def test_the_body_does_not_leak_the_error_text(serve):
    server = await serve({"postgres": failing("password=hunter2 refused")})

    _, body = await get(server)

    assert b"hunter2" not in body


async def test_a_dependency_that_hangs_counts_as_down(serve):
    async def hang():
        await asyncio.sleep(60)

    server = await serve({"redis": hang, "postgres": ok}, timeout=0.2)

    status, body = await get(server)

    assert (status, json.loads(body)["failing"]) == (503, ["redis"])


async def test_other_paths_and_methods_are_refused(serve):
    server = await serve({"redis": ok})

    assert (await get(server, "/metrics"))[0] == 404
    assert (await get(server, "/health", method="POST"))[0] == 405


async def test_health_reports_redis_down_during_an_outage_and_ok_after(redis, proxy, serve):
    import redis.asyncio as aioredis

    client = aioredis.from_url(proxy.url, socket_connect_timeout=0.5, socket_timeout=0.5)
    server = await serve({"redis": lambda: check_redis(client)})
    assert (await get(server))[0] == 200

    await proxy.stop()
    status, body = await get(server)
    assert (status, json.loads(body)["failing"]) == (503, ["redis"])

    await proxy.start()
    assert (await get(server))[0] == 200
    await client.aclose()


async def test_the_verdict_is_cached_so_the_checks_do_not_follow_the_request_rate():
    calls = []

    async def counting():
        calls.append(1)

    server = await serve_health({"x": counting}, host="127.0.0.1", port=0, cache_ttl=30.0)
    try:
        for _ in range(3):
            assert (await get(server))[0] == 200
    finally:
        server.close()

    assert len(calls) == 1


async def test_the_verdict_is_rechecked_after_the_cache_expires():
    calls = []

    async def counting():
        calls.append(1)

    server = await serve_health({"x": counting}, host="127.0.0.1", port=0, cache_ttl=0.05)
    try:
        await get(server)
        await asyncio.sleep(0.1)
        await get(server)
    finally:
        server.close()

    assert len(calls) == 2
