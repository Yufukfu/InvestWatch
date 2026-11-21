"""Shared test fixtures: a local HTTP stub server that records what it receives, and the service-backed
fixtures for the ingest tests.

The ingest tests need PostgreSQL, Redis and MinIO. Their addresses come from the environment
(`IW_TEST_PG_DSN`, `IW_TEST_REDIS_URL`, `IW_TEST_MINIO_*`); without them those tests are skipped, so the
pure-logic tests still run anywhere.
"""

import asyncio
import json
import os
import threading
import time
import uuid
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import asyncpg
import jsonschema
import pytest
import pytest_asyncio
import redis.asyncio as aioredis
from arq.connections import RedisSettings, create_pool
from arq.worker import Worker

from iw_scraper.config import contracts_dir
from iw_scraper.jobs import QueueSettings, job_function
from iw_scraper.types import JobError, Source


@dataclass
class Route:
    status: int = 200
    body: bytes = b""
    headers: dict[str, str] = field(default_factory=dict)
    delay: float = 0.0


@dataclass(frozen=True)
class Received:
    path: str
    headers: tuple[tuple[str, str], ...]  # in wire order
    connect: bool  # True for a CONNECT request: the client is using this server as its proxy


class Stub:
    """Routes are set per test; every request is logged."""

    def __init__(self) -> None:
        self.routes: dict[str, Route] = {}
        self.requests: list[Received] = []
        self.connect_status = 200  # what a CONNECT gets; 407 plays a proxy that refuses our credentials
        stub = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"  # keep-alive, so a tunnelled request follows a CONNECT

            def log_message(self, *args) -> None:  # silence the default stderr log
                pass

            def do_CONNECT(self) -> None:
                stub.requests.append(Received(self.path, tuple(self.headers.items()), True))
                if stub.connect_status != 200:
                    self.send_response(stub.connect_status)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                self.send_response(200, "Connection established")
                self.end_headers()  # the next request on this socket is the tunnelled one

            def do_GET(self) -> None:
                stub.requests.append(Received(self.path, tuple(self.headers.items()), False))
                route = stub.routes.get(self.path, Route(status=404, body=b"not found"))
                time.sleep(route.delay)
                try:
                    self.send_response(route.status)
                    for name, value in route.headers.items():
                        self.send_header(name, value)
                    self.send_header("Content-Length", str(len(route.body)))
                    self.end_headers()
                    self.wfile.write(route.body)
                except (BrokenPipeError, ConnectionResetError):  # the client gave up (timeout test)
                    pass

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._server.daemon_threads = True
        self.port = self._server.server_address[1]
        threading.Thread(target=self._server.serve_forever, daemon=True).start()

    def route(
        self,
        path: str,
        *,
        status: int = 200,
        body: bytes = b"",
        content_type: str | None = "text/html; charset=utf-8",
        headers: dict[str, str] | None = None,
        delay: float = 0.0,
    ) -> None:
        all_headers = dict(headers or {})
        if content_type is not None:
            all_headers["Content-Type"] = content_type
        self.routes[path] = Route(status=status, body=body, headers=all_headers, delay=delay)

    def url(self, path: str = "/", host: str = "127.0.0.1") -> str:
        return f"http://{host}:{self.port}{path}"

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()


@pytest.fixture
def stub():
    server = Stub()
    yield server
    server.close()


@pytest.fixture
def stub2():
    """A second server, for tests that need two proxies."""
    server = Stub()
    yield server
    server.close()


SCHEMA_SQL = (Path(__file__).parent / "schema.sql").read_text()


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        message = f"{name} not set (needs the test containers)"
        if os.environ.get("CI"):
            # in CI a skipped service test would hide the core spec scenarios behind a green run
            pytest.fail(message)
        pytest.skip(message)
    return value


@pytest_asyncio.fixture
async def pool():
    """A pool on a fresh, throwaway schema (dropped afterwards)."""
    dsn = _require("IW_TEST_PG_DSN")
    schema = f"t_{uuid.uuid4().hex[:12]}"
    admin = await asyncpg.connect(dsn)
    await admin.execute(f'CREATE SCHEMA "{schema}"')
    created = await asyncpg.create_pool(dsn, min_size=1, max_size=4, server_settings={"search_path": schema})
    async with created.acquire() as conn:
        await conn.execute(SCHEMA_SQL)
    try:
        yield created
    finally:
        await created.close()
        await admin.execute(f'DROP SCHEMA "{schema}" CASCADE')
        await admin.close()


@pytest_asyncio.fixture
async def redis_client():
    """A Redis client; tests use their own stream name, so nothing is shared between tests."""
    from redis import asyncio as aioredis

    client = aioredis.from_url(_require("IW_TEST_REDIS_URL"), decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()


@pytest.fixture
def stream_name() -> str:
    return f"iw:documents:test:{uuid.uuid4().hex[:8]}"


@pytest_asyncio.fixture
async def storage():
    """A Storage on a unique bucket. The bucket is made here, as Damian's `minio-init` does in the stack:
    the service itself never creates it."""
    import asyncio

    from iw_scraper.ingest.storage import Storage

    store = Storage(
        _require("IW_TEST_MINIO_ENDPOINT"),
        os.environ["IW_TEST_MINIO_ACCESS_KEY"],
        os.environ["IW_TEST_MINIO_SECRET_KEY"],
        bucket=f"iw-raw-test-{uuid.uuid4().hex[:10]}",
    )
    await asyncio.to_thread(store._client.make_bucket, store.bucket)
    try:
        yield store
    finally:
        for key in await store.list_keys():
            await store.remove(key)
        await asyncio.to_thread(store._client.remove_bucket, store.bucket)


@pytest.fixture
def source() -> Source:
    return Source(
        id=str(uuid.uuid4()),
        name="Alfa",
        platform="web",
        url="https://alfa.example.com/",
        source_kind="firm_own",
        target_modules=("M2",),
        active=True,
    )


@pytest_asyncio.fixture
async def seeded_source(pool, source):
    """The `sources` row that `documents.source_id` points at."""
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO sources (id, name, platform, url, source_kind, target_modules) VALUES ($1, $2, $3, $4, $5, $6)",
            uuid.UUID(source.id), source.name, source.platform, source.url, source.source_kind,
            ["M3"],
        )
    return source


# --- queue and orchestration fixtures (scraper-orchestration) ---

@pytest.fixture
async def redis():
    """A real Redis (REDIS_URL, see scraper/compose.test.yaml), emptied around each test."""
    pool = await create_pool(RedisSettings.from_dsn(os.environ["REDIS_URL"]))
    await pool.flushdb()
    yield pool
    await pool.flushdb()
    await pool.aclose()


def fast_settings(**overrides) -> QueueSettings:
    base = dict(
        max_tries=3,
        backoff_base=0.05,
        backoff_cap=0.5,
        attempt_timeout=5.0,
        domain_concurrency=2,
        lease_ttl=1.0,
        requeue_delay=0.05,
        failure_threshold=5,
        domain_cooldown=0.5,
    )
    return QueueSettings(**{**base, **overrides})


@dataclass
class Recorder:
    """Stands in for the collector stages and the job-error sink."""

    errors: list[JobError] = field(default_factory=list)

    async def record_error(self, error: JobError) -> None:
        self.errors.append(error)


def make_source(source_id, *, active=True, platform="web", cron=None, url="https://example.test/page") -> Source:
    return Source(
        id=source_id, name="s", platform=platform, url=url, source_kind="firm_own",
        target_modules=("M1",), active=active, schedule_cron=cron,
    )


class FakeSourceStore:
    """In-memory `sources` table. `permissive` makes any unknown id an active web source."""

    def __init__(self) -> None:
        self.sources: dict[str, Source] = {}
        self.status: dict[str, dict] = {}
        self.permissive = True

    async def get(self, source_id):
        if source_id in self.sources:
            return self.sources[source_id]
        return make_source(source_id) if self.permissive else None

    async def mark_running(self, source_id) -> None:
        self.status[source_id] = {"last_run_status": "running"}

    async def mark_finished(self, source_id, *, at: datetime, status: str) -> None:
        self.status[source_id] = {"last_run_at": at, "last_run_status": status}

    async def schedulable(self):
        return list(self.sources.values())


@pytest.fixture
def store() -> FakeSourceStore:
    return FakeSourceStore()


_EVENT_SCHEMA = json.loads((contracts_dir() / "schemas" / "events.schema.json").read_text())
_EVENT_VALIDATOR = jsonschema.Draft202012Validator({"$ref": "#/$defs/event", "$defs": _EVENT_SCHEMA["$defs"]})


@pytest.fixture
async def events():
    """Everything published on Pub/Sub `iw:events`, each message checked against the contract."""
    client = aioredis.from_url(os.environ["REDIS_URL"])
    pubsub = client.pubsub()
    await pubsub.subscribe("iw:events")
    received: list[dict] = []

    async def pump():
        async for message in pubsub.listen():
            if message["type"] == "message":
                body = json.loads(message["data"])
                _EVENT_VALIDATOR.validate(body)
                received.append(body)

    task = asyncio.create_task(pump())
    await asyncio.sleep(0.1)
    yield received
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    await pubsub.aclose()
    await client.aclose()


@pytest.fixture
async def start_worker(store):
    """Start in-process arq workers (each with its own Redis pool); returns the worker's task."""
    started: list[tuple[Worker, asyncio.Task]] = []

    def start(run_source, recorder: Recorder, settings: QueueSettings, **worker_kwargs) -> asyncio.Task:
        worker = Worker(
            functions=[job_function(settings)],
            redis_settings=RedisSettings.from_dsn(os.environ["REDIS_URL"]),
            ctx={"settings": settings, "run_source": run_source, "record_error": recorder.record_error, "sources": store},
            poll_delay=0.02,
            max_jobs=worker_kwargs.pop("max_jobs", 10),
            handle_signals=False,
            **worker_kwargs,
        )
        task = asyncio.create_task(worker.async_run())
        started.append((worker, task))
        return task

    yield start
    for worker, task in started:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await worker.close()


class TcpProxy:
    """A TCP forwarder in front of Redis that a test can switch off and on, to simulate an outage."""

    def __init__(self, target_host: str, target_port: int) -> None:
        self._target = (target_host, target_port)
        self._server: asyncio.Server | None = None
        self._writers: set[asyncio.StreamWriter] = set()
        self.port = 0

    @property
    def url(self) -> str:
        return f"redis://127.0.0.1:{self.port}/0"

    async def start(self) -> None:
        self._server = await asyncio.start_server(self._serve, "127.0.0.1", self.port)
        self.port = self._server.sockets[0].getsockname()[1]

    async def stop(self) -> None:
        if self._server:
            self._server.close()
        for writer in list(self._writers):  # 3.12's wait_closed() waits for open connections
            writer.close()
        self._writers.clear()
        if self._server:
            await self._server.wait_closed()
            self._server = None

    async def _serve(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            upstream_reader, upstream_writer = await asyncio.open_connection(*self._target)
        except OSError:
            writer.close()
            return
        self._writers.update({writer, upstream_writer})

        async def pipe(source: asyncio.StreamReader, sink: asyncio.StreamWriter) -> None:
            try:
                while data := await source.read(65536):
                    sink.write(data)
                    await sink.drain()
            except (ConnectionError, OSError):
                pass
            finally:
                sink.close()

        await asyncio.gather(pipe(reader, upstream_writer), pipe(upstream_reader, writer))


@pytest.fixture
async def proxy():
    from urllib.parse import urlsplit

    target = urlsplit(os.environ["REDIS_URL"])
    forwarder = TcpProxy(target.hostname, target.port or 6379)
    await forwarder.start()
    yield forwarder
    await forwarder.stop()
