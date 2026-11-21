"""`GET /health`: 200 when every dependency answers, 503 naming the ones that do not."""

import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable, Mapping

logger = logging.getLogger(__name__)

Check = Callable[[], Awaitable[None]]
REQUEST_LINE_TIMEOUT = 5.0
REASONS = {200: "OK", 404: "Not Found", 405: "Method Not Allowed", 503: "Service Unavailable"}


async def serve_health(
    checks: Mapping[str, Check],
    *,
    host: str = "0.0.0.0",
    port: int = 8080,
    timeout: float = 2.0,
    cache_ttl: float = 3.0,
    clock=time.monotonic,
) -> asyncio.Server:
    """Start the endpoint. A check raises when its dependency is down; one that hangs counts as down.

    The verdict is kept for `cache_ttl` seconds and a burst shares one run of the checks, so the load on the
    stores does not follow the request rate of an unauthenticated endpoint.
    """
    cached: tuple[float, tuple[int, dict]] | None = None
    in_flight = asyncio.Lock()

    async def verdict() -> tuple[int, dict]:
        nonlocal cached
        async with in_flight:
            if cached is None or clock() - cached[0] >= cache_ttl:
                cached = (clock(), await _verdict(checks, timeout))
            return cached[1]

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            request_line = await asyncio.wait_for(reader.readline(), REQUEST_LINE_TIMEOUT)
            status, body = _refusal(request_line) or await verdict()
            payload = json.dumps(body).encode()
            head = f"HTTP/1.1 {status} {REASONS[status]}\r\nContent-Type: application/json\r\n"
            head += f"Content-Length: {len(payload)}\r\nConnection: close\r\n"
            head += "Allow: GET\r\n\r\n" if status == 405 else "\r\n"
            writer.write(head.encode() + payload)
            await writer.drain()
        except (TimeoutError, ConnectionError, ValueError):
            pass  # a client that sends junk or leaves is not worth a log line
        finally:
            writer.close()

    return await asyncio.start_server(handle, host, port)


async def check_redis(redis) -> None:
    if not await redis.ping():
        raise ConnectionError("redis did not answer PING")


def _refusal(request_line: bytes) -> tuple[int, dict] | None:
    """The answer for a request that is not `GET /health`; None for one that is."""
    parts = request_line.decode("latin-1").split()
    if len(parts) < 2:
        return 404, {"status": "not found"}
    method, target = parts[0], parts[1].split("?")[0]
    if target != "/health":
        return 404, {"status": "not found"}
    if method != "GET":
        return 405, {"status": "method not allowed"}
    return None


async def _verdict(checks: Mapping[str, Check], timeout: float) -> tuple[int, dict]:
    results = await asyncio.gather(*(_run(name, check, timeout) for name, check in checks.items()))
    failing = sorted(name for name, healthy in results if not healthy)
    if failing:
        return 503, {"status": "unavailable", "failing": failing}
    return 200, {"status": "ok"}


async def _run(name: str, check: Check, timeout: float) -> tuple[str, bool]:
    try:
        await asyncio.wait_for(check(), timeout)
    except Exception as error:  # noqa: BLE001 - any failure of a check means the dependency is down
        logger.warning("health check %s failed: %s", name, type(error).__name__)  # not the text: it may hold a DSN
        return name, False
    return name, True
