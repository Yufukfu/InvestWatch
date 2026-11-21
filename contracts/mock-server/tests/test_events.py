"""Socket.IO /events against a real uvicorn server on a free port."""

from __future__ import annotations

import threading
import time
from collections import defaultdict

import httpx
import pytest
import socketio
import uvicorn

from conftest import assert_valid
from iw_mock_server.events import create_asgi_app
from iw_mock_server.settings import Settings

ADMIN = {"X-Mock-Admin": "1"}  # /__mock/* needs it (forces a CORS preflight)
EVENT_TYPES = ("finding.created", "finding.high_risk", "finding.updated", "scan.started", "scan.finished")


class LiveServer:
    def __init__(self, settings: Settings):
        config = uvicorn.Config(create_asgi_app(settings), host="127.0.0.1", port=0, log_level="warning",
                                lifespan="on", timeout_graceful_shutdown=1)
        self.server = uvicorn.Server(config)
        self.thread = threading.Thread(target=self.server.run, daemon=True)

    def __enter__(self) -> str:
        self.thread.start()
        deadline = time.time() + 10
        while not self.server.started:
            if time.time() > deadline:
                raise RuntimeError("server did not start")
            time.sleep(0.05)
        port = self.server.servers[0].sockets[0].getsockname()[1]
        return f"http://127.0.0.1:{port}"

    def __exit__(self, *exc):
        self.server.should_exit = True
        self.thread.join(timeout=10)


class Recorder:
    def __init__(self, url: str):
        self.events: dict[str, list] = defaultdict(list)
        self.order: list[str] = []  # event types in arrival order
        self.cond = threading.Condition()
        self.sio = socketio.Client()
        for event_type in EVENT_TYPES:
            self.sio.on(event_type, self._handler(event_type), namespace="/events")
        self.sio.connect(url, namespaces=["/events"], transports=["websocket"], wait_timeout=10)

    def _handler(self, event_type):
        def handle(data):
            with self.cond:
                self.events[event_type].append(data)
                self.order.append(event_type)
                self.cond.notify_all()
        return handle

    def wait_for(self, event_type: str, count: int = 1, timeout: float = 5) -> list:
        with self.cond:
            self.cond.wait_for(lambda: len(self.events[event_type]) >= count, timeout=timeout)
            return list(self.events[event_type])

    def close(self):
        self.sio.disconnect()


def assert_event_valid(event_type: str, data) -> None:
    assert_valid("events", {"type": event_type, "emitted_at": "2026-11-21T12:00:00Z", "data": data})


@pytest.fixture
def live(contracts_dir):
    # websocket-client sends the server's own URL as Origin, which is unknown before start-up (port 0)
    settings = Settings(contracts_dir=contracts_dir, replay_interval_s=0, scan_delay_s=0.2, cors_origins=("*",))
    with LiveServer(settings) as url:
        recorder = Recorder(url)
        yield url, recorder
        recorder.close()


def test_status_change_emits_finding_updated(live):
    url, rec = live
    finding = httpx.get(f"{url}/api/findings").json()["items"][0]

    httpx.patch(f"{url}/api/findings/{finding['id']}", json={"status": "in_review"})

    events = rec.wait_for("finding.updated")
    assert events == [{"id": finding["id"], "status": "in_review"}]
    assert_event_valid("finding.updated", events[0])


NEW_SOURCE = {"name": "Skan testowy", "platform": "web", "url": "https://scan-test.example.com/",
              "source_kind": "unknown", "target_modules": ["M3"], "active": True}


def test_scan_emits_started_then_finished_and_updates_the_source(live):
    url, rec = live
    source_id = httpx.post(f"{url}/api/sources", json=NEW_SOURCE).json()["id"]  # never scanned yet

    assert httpx.post(f"{url}/api/scans", json={"source_id": source_id}).status_code == 202

    finished = rec.wait_for("scan.finished")
    started = rec.wait_for("scan.started")
    assert rec.order.index("scan.started") < rec.order.index("scan.finished")
    assert started[0]["source_id"] == finished[0]["source_id"] == source_id
    assert finished[0]["status"] == "ok"
    assert_event_valid("scan.started", started[0])
    assert_event_valid("scan.finished", finished[0])
    source = next(s for s in httpx.get(f"{url}/api/sources").json()["items"] if s["id"] == source_id)
    assert source["last_run_status"] == "ok" and source["last_run_at"] is not None


def test_scan_in_flight_does_not_write_into_a_reset_store(contracts_dir):
    # a long scan delay so the reset reliably lands while the scan is sleeping
    settings = Settings(contracts_dir=contracts_dir, replay_interval_s=0, scan_delay_s=1.5, cors_origins=("*",))
    with LiveServer(settings) as url:
        rec = Recorder(url)
        source = httpx.get(f"{url}/api/sources").json()["items"][0]

        httpx.post(f"{url}/api/scans", json={"source_id": source["id"]})
        rec.wait_for("scan.started")
        httpx.post(f"{url}/__mock/reset", headers=ADMIN)
        assert rec.wait_for("scan.finished", timeout=5)

        after = next(s for s in httpx.get(f"{url}/api/sources").json()["items"] if s["id"] == source["id"])
        rec.close()

    assert after == source


def test_unknown_scan_emits_nothing(live):
    url, rec = live

    assert httpx.post(f"{url}/api/scans", json={"source_id": "00000000-0000-4000-8000-000000000000"}).status_code == 404

    assert rec.wait_for("scan.started", timeout=0.5) == []


def test_mock_emit_creates_a_finding_and_events(live):
    url, rec = live
    before = httpx.get(f"{url}/api/findings").json()["total"]

    r = httpx.post(f"{url}/__mock/emit", headers=ADMIN)

    assert r.status_code == 200
    created = rec.wait_for("finding.created")
    assert_event_valid("finding.created", created[0])
    assert created[0]["id"] == r.json()["id"]
    listed = httpx.get(f"{url}/api/findings").json()
    assert listed["total"] == before + 1
    assert listed["items"][0]["id"] == created[0]["id"]  # newest first


def test_high_risk_event_only_above_threshold(live):
    url, rec = live
    httpx.put(f"{url}/api/settings/thresholds", json={"M1": 0, "M2": 0, "M3": 0})

    httpx.post(f"{url}/__mock/emit", headers=ADMIN)
    high = rec.wait_for("finding.high_risk")
    assert len(high) == 1
    assert_event_valid("finding.high_risk", high[0])

    httpx.put(f"{url}/api/settings/thresholds", json={"M1": 1, "M2": 1, "M3": 1})
    httpx.post(f"{url}/__mock/emit", headers=ADMIN)
    rec.wait_for("finding.created", count=2)
    assert len(rec.wait_for("finding.high_risk", count=2, timeout=0.5)) == 1


def test_replay_disabled_emits_nothing_on_its_own(live):
    _, rec = live

    assert rec.wait_for("finding.created", timeout=1) == []


def test_replay_emits_periodically_and_survives_a_disconnect(contracts_dir):
    settings = Settings(contracts_dir=contracts_dir, replay_interval_s=0.2, scan_delay_s=0, cors_origins=("*",))
    with LiveServer(settings) as url:
        first, second = Recorder(url), Recorder(url)
        assert len(first.wait_for("finding.created", count=1)) >= 1
        first.close()
        assert len(second.wait_for("finding.created", count=3)) >= 3
        second.close()


def test_replay_pauses_while_no_client_is_connected(contracts_dir):
    settings = Settings(contracts_dir=contracts_dir, replay_interval_s=0.1, scan_delay_s=0, cors_origins=("*",))
    with LiveServer(settings) as url:
        rec = Recorder(url)
        rec.wait_for("finding.created", count=2)
        rec.close()
        time.sleep(0.3)  # let an in-flight replay finish
        total = httpx.get(f"{url}/api/findings").json()["total"]
        time.sleep(1.0)  # ten intervals with nobody connected

        assert httpx.get(f"{url}/api/findings").json()["total"] == total


def test_every_route_runs_on_the_event_loop(contracts_dir):
    """Plain `def` routes run in FastAPI's thread pool and race with replay writes on the loop."""
    import inspect

    from iw_mock_server.app import create_app

    api = create_app(Settings(contracts_dir=contracts_dir, replay_interval_s=0))
    sync_routes = [r.path for r in api.routes
                   if getattr(r, "endpoint", None) and r.path.startswith(("/api", "/__mock"))
                   and not inspect.iscoroutinefunction(r.endpoint)]

    assert sync_routes == []


def test_reads_stay_consistent_while_replay_writes(contracts_dir):
    """Reads must never see the store mid-update (was: 'dictionary changed size during iteration')."""
    settings = Settings(contracts_dir=contracts_dir, replay_interval_s=0, scan_delay_s=0, cors_origins=("*",))
    with LiveServer(settings) as url:
        errors: list[int] = []
        stop = threading.Event()

        def writer():
            with httpx.Client() as c:
                while not stop.is_set():
                    c.post(f"{url}/__mock/emit", headers=ADMIN)

        def reader(path: str):
            with httpx.Client() as c:
                while not stop.is_set():
                    r = c.get(f"{url}{path}")
                    if r.status_code != 200:
                        errors.append(r.status_code)

        threads = [threading.Thread(target=writer) for _ in range(3)]
        threads += [threading.Thread(target=reader, args=(p,)) for p in
                    ("/api/findings?q=x&page_size=200", "/api/stats/trend?risk_level=high", "/api/stats/summary")]
        for t in threads:
            t.start()
        time.sleep(4)
        stop.set()
        for t in threads:
            t.join(timeout=10)

        assert errors == []


def test_socketio_cors_allows_only_configured_origins(contracts_dir):
    settings = Settings(contracts_dir=contracts_dir, replay_interval_s=0, cors_origins=("http://localhost:5173",))
    with LiveServer(settings) as url:
        allowed = httpx.get(f"{url}/socket.io/?EIO=4&transport=polling", headers={"Origin": "http://localhost:5173"})
        other = httpx.get(f"{url}/socket.io/?EIO=4&transport=polling", headers={"Origin": "http://evil.example"})

    assert allowed.status_code == 200
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert other.status_code == 400


def test_source_is_running_while_its_scan_is_in_flight(contracts_dir):
    settings = Settings(contracts_dir=contracts_dir, replay_interval_s=0, scan_delay_s=1.5, cors_origins=("*",))
    with LiveServer(settings) as url:
        rec = Recorder(url)
        source_id = httpx.post(f"{url}/api/sources", json=NEW_SOURCE).json()["id"]

        httpx.post(f"{url}/api/scans", json={"source_id": source_id})
        running = next(s for s in httpx.get(f"{url}/api/sources").json()["items"] if s["id"] == source_id)
        rec.wait_for("scan.finished", timeout=5)
        done = next(s for s in httpx.get(f"{url}/api/sources").json()["items"] if s["id"] == source_id)
        rec.close()

    assert running["last_run_status"] == "running"  # the contract enum has "running" for this window
    assert_valid("source", running)
    assert done["last_run_status"] == "ok"
