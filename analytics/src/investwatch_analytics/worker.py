"""Redis Stream worker: `iw:documents` (group `analytics`) -> findings in Postgres -> events on `iw:events`.

Per message: load the document, run the pure pipeline, save all findings in one transaction, publish the events,
and only then XACK (`.docs/integration-plan.md` §2, points 3-5). A redelivery is safe because the store upserts on
`(document_id, module)` and an `updated` finding publishes nothing. Poison messages are acked with a reason so they
never block the stream; an outage of Redis or Postgres is retried with capped backoff and never acked.
Spec: openspec/specs/document-stream-worker/spec.md.

Run: `python -m investwatch_analytics.worker` (env: see `config.WorkerSettings` and `analytics/.env.example`).
"""

from __future__ import annotations

import logging
import random
import re
import signal
import sys
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import redis

from . import logging_setup
from .config import ConfigError, LlmSettings, Settings, WorkerSettings, registry_provenance, uses_seed_registry
from .llm import build_judge
from .events import Publisher, RedisPublisher
from .health import start_health_server
from .pipeline import analyze, default_signal_catalogues
from .registry import Registry, RegistryError
from .rules.engine import Catalogue, CatalogueError
from .storage import InvalidDocument, NotFound, StoreMisconfigured, StoreUnavailable

log = logging.getLogger(__name__)

STREAM = "iw:documents"
GROUP = "analytics"
SCHEMA_VERSION = "v1"
_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
BACKOFF_START_S = 1
BACKOFF_CAP_S = 30
CLAIM_COUNT = 10


class StopRequested(BaseException):
    """Raised by the signal handler only while the worker idles in XREADGROUP, to leave the wait at once.
    A BaseException (like KeyboardInterrupt), so no `except Exception` on the way can swallow it."""


@dataclass(frozen=True)
class WorkerConfig:
    consumer: str
    block_ms: int = 5000
    claim_min_idle_ms: int = 60000
    max_deliveries: int = 5
    stream: str = STREAM


class Worker:
    def __init__(
        self,
        client: Any,
        store: Any,
        publisher: Publisher,
        *,
        registry: Registry,
        catalogue: Catalogue,
        config: WorkerConfig,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        sleep: Callable[[float], None] | None = None,
        jitter: Callable[[], float] = lambda: random.uniform(0, 0.5),
        judge: Any = None,
    ) -> None:
        self._judge = judge  # an LlmJudge or None (rules-only); the only extra I/O analyze() may do
        self._redis = client
        self._store = store
        self._publisher = publisher
        self._registry = registry
        self._catalogue = catalogue
        self._config = config
        self._now = now
        self._stop_event = threading.Event()
        # Default: an Event wait, so SIGTERM cuts a 30 s backoff short (time.sleep would run to the end, PEP 475,
        # and Docker's 10 s stop grace would SIGKILL the container).
        self._sleep = sleep or self._stop_event.wait
        self._jitter = jitter
        self._stop = False
        self._idle_read = False
        self._backoff = BACKOFF_START_S

    # -- lifecycle ---------------------------------------------------------------------------------

    def request_stop(self) -> None:
        """Called from a signal handler: finish the current message, then leave `run`."""
        self._stop = True
        self._stop_event.set()

    def handle_signal(self) -> None:
        """SIGTERM / SIGINT. While idle in XREADGROUP nothing is in flight, so the blocking read is abandoned at
        once (a message the server handed over in that instant stays pending and is reclaimed later). While a
        message is being processed only the flag is set and that message finishes. Docker Desktop stops
        containers after 1 s, Linux after 10 s; a full STREAM_BLOCK_MS wait would be SIGKILLed on the former."""
        first = not self._stop
        self.request_stop()
        if first and self._idle_read:  # a second signal (e.g. during cleanup) never raises
            raise StopRequested

    def ensure_group(self) -> None:
        """Create the stream and the group from id 0 (backlog included); an existing group is success."""
        while True:
            try:
                self._redis.xgroup_create(self._config.stream, GROUP, id="0", mkstream=True)
                break
            except redis.ResponseError as exc:
                if "BUSYGROUP" not in str(exc):
                    raise
                break
            except (redis.ConnectionError, redis.TimeoutError) as exc:
                self._back_off("redis_unavailable", exc)
                if self._stop:
                    return
        self._backoff = BACKOFF_START_S

    def run(self, max_iterations: int | None = None) -> None:
        """Main loop. Outages back off and retry; `StoreMisconfigured` propagates (the process must exit)."""
        iterations = 0
        while not self._stop and (max_iterations is None or iterations < max_iterations):
            iterations += 1
            try:
                self.run_once()
                self._backoff = BACKOFF_START_S
            except StopRequested:
                return
            except (redis.ConnectionError, redis.TimeoutError) as exc:
                self._back_off("redis_unavailable", exc)
            except redis.ResponseError as exc:
                if "NOGROUP" in str(exc):  # stream or group deleted under us: recreate and carry on
                    log.warning("consumer group missing, recreating", extra={"reason": "group_missing"})
                    self.ensure_group()
                else:  # e.g. READONLY during a failover: transient
                    self._back_off("redis_unavailable", exc)
            except StoreUnavailable as exc:
                self._back_off("db_unavailable", exc)
            except StoreMisconfigured:
                raise  # not retryable: main() exits with code 2
            except Exception as exc:  # last resort: never crash-loop on something the loop did not foresee
                log.error("unexpected error in the worker loop", exc_info=True,
                          extra={"reason": "unexpected_error", "error": type(exc).__name__})
                self._back_off("unexpected_error", exc)

    def run_once(self) -> int:
        """Reclaim stale messages, else read one new message; process each. Returns how many were handled."""
        handled = 0
        _, claimed, _ = self._redis.xautoclaim(
            self._config.stream, GROUP, self._config.consumer,
            min_idle_time=self._config.claim_min_idle_ms, start_id="0-0", count=CLAIM_COUNT,
        )
        for message_id, fields in claimed:
            if self._stop:
                return handled
            self._process(message_id, fields or {})
            handled += 1
        if handled or self._stop:
            return handled
        self._idle_read = True
        try:
            response = self._redis.xreadgroup(
                GROUP, self._config.consumer, {self._config.stream: ">"}, count=1, block=self._config.block_ms
            )
        finally:
            self._idle_read = False
        for _stream, messages in response or []:
            for message_id, fields in messages:
                self._process(message_id, fields or {})
                handled += 1
        return handled

    def _back_off(self, reason: str, exc: BaseException) -> None:
        delay = self._backoff + self._jitter()
        log.warning("dependency unavailable, backing off",
                    extra={"reason": reason, "error": str(exc), "backoff_s": delay})
        self._sleep(delay)
        self._backoff = min(self._backoff * 2, BACKOFF_CAP_S)

    # -- one message -------------------------------------------------------------------------------

    def _deliveries(self, message_id: str) -> int:
        entries = self._redis.xpending_range(self._config.stream, GROUP, min=message_id, max=message_id, count=1)
        return int(entries[0]["times_delivered"]) if entries else 1

    def _ack(self, message_id: str) -> None:
        self._redis.xack(self._config.stream, GROUP, message_id)

    def _outcome(self, level: int, outcome: str, message_id: str, started: float, **extra: Any) -> None:
        log.log(level, "message handled", exc_info=extra.pop("exc_info", None), extra={
            "outcome": outcome, "stream_id": message_id,
            "duration_ms": round((time.perf_counter() - started) * 1000, 1), **extra,
        })

    def _process(self, message_id: str, fields: Mapping[str, Any]) -> None:
        started = time.perf_counter()
        document_id = fields.get("document_id")
        if (set(fields) != {"document_id", "schema"} or fields.get("schema") != SCHEMA_VERSION
                or not isinstance(document_id, str) or not _UUID.match(document_id)):
            self._ack(message_id)
            known = {"document_id": document_id} if isinstance(document_id, str) and _UUID.match(document_id) else {}
            self._outcome(logging.WARNING, "invalid_message", message_id, started,
                          fields=sorted(str(k) for k in fields), **known)
            return
        try:
            doc = self._store.load_document(document_id)
        except NotFound:
            self._ack(message_id)
            self._outcome(logging.WARNING, "document_not_found", message_id, started, document_id=document_id)
            return
        except InvalidDocument as exc:
            self._ack(message_id)
            self._outcome(logging.WARNING, "invalid_document", message_id, started,
                          document_id=document_id, field=exc.field)
            return
        except (StoreUnavailable, StoreMisconfigured):
            raise
        except Exception as exc:  # anything unexpected: retried, then acked at MAX_DELIVERIES
            self._unexpected(message_id, document_id, started, exc)
            return
        try:
            findings = analyze(doc, registry=self._registry, catalogue=self._catalogue, now=self._now(),
                               judge=self._judge)
            saved = self._store.save_findings(doc, findings) if findings else []
        except (StoreUnavailable, StoreMisconfigured):
            raise
        except Exception as exc:
            self._unexpected(message_id, document_id, started, exc)
            return
        if saved:
            try:
                self._publisher.publish_findings(saved)
            except Exception:  # findings are committed; events are at most once (RedisError is handled inside)
                log.warning("event publish failed; findings stay committed", exc_info=True, extra={
                    "reason": "publish_failed", "finding_ids": [s.finding.id for s in saved if s.outcome == "created"],
                })
        self._ack(message_id)
        created = sum(s.outcome == "created" for s in saved)
        self._outcome(logging.INFO, "stored" if saved else "no_findings", message_id, started,
                      document_id=document_id, findings_created=created,
                      findings_updated=len(saved) - created)

    def _unexpected(self, message_id: str, document_id: str, started: float, exc: Exception) -> None:
        deliveries = self._deliveries(message_id)
        if deliveries >= self._config.max_deliveries:
            self._ack(message_id)
            self._outcome(logging.ERROR, "max_deliveries_exceeded", message_id, started, document_id=document_id,
                          deliveries=deliveries, error=type(exc).__name__, exc_info=exc)
        else:
            self._outcome(logging.ERROR, "retry_later", message_id, started, document_id=document_id,
                          deliveries=deliveries, error=type(exc).__name__, exc_info=exc)


# ---- entry point -----------------------------------------------------------------------------------


def stream_client(url: str, block_ms: int) -> redis.Redis:
    """The worker's Redis client. `encoding_errors="replace"`: a stream entry with bytes that are not UTF-8 must
    decode (and then fail the message checks as `invalid_message`), never raise while the reply is read, which
    would leave the entry pending and crash-loop the worker on every reclaim."""
    return redis.Redis.from_url(url, decode_responses=True, encoding_errors="replace",
                                socket_timeout=(block_ms / 1000) + 5, socket_connect_timeout=5,
                                health_check_interval=30)


def install_signal_handlers(worker: Worker) -> None:
    """SIGTERM (docker stop) and SIGINT (Ctrl+C) both go to `Worker.handle_signal`."""
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: worker.handle_signal())


def main(env: Mapping[str, str] | None = None) -> int:
    """Start the worker. Returns the process exit code: 0 after a clean stop, 2 on a configuration error."""
    import os

    env = os.environ if env is None else env
    logging_setup.configure((env.get("LOG_LEVEL") or "INFO").upper() if (env.get("LOG_LEVEL") or "INFO").upper()
                            in logging.getLevelNamesMapping() else "INFO")
    from .storage import PostgresStore

    try:
        worker_settings = WorkerSettings.from_env(env)
        settings = Settings.from_env(env)
        llm_settings = LlmSettings.from_env(env, claim_min_idle_ms=worker_settings.claim_min_idle_ms)
        # Mode only: never the URL (it could carry a host the operator considers private) or the key.
        log.info("llm configured", extra={"llm_mode": llm_settings.mode, "llm_model": llm_settings.model or None})
        registry = Registry.from_csv(settings.registry_csv)
        meta = registry_provenance(settings.registry_csv)
        # The snapshot date is logged so it can be shown to users later; its age is never a warning.
        log.info("registry loaded", extra={"reason": "registry_loaded", "registry_csv": str(settings.registry_csv),
                                           "firms": len(registry.firms),
                                           "snapshot_date": (meta or {}).get("fetched_at")})
        if uses_seed_registry(settings):
            log.warning("bundled fictional registry in use: R1 and high-risk alerts for real firms are not "
                        "meaningful until REGISTRY_CSV names a real KNF registry",
                        extra={"reason": "registry_seed", "registry_csv": str(settings.registry_csv)})
        elif meta is None:
            log.warning("registry without provenance: no knf.meta.json next to it",
                        extra={"reason": "registry_unverified", "registry_csv": str(settings.registry_csv)})
        catalogue = Catalogue.load()
        default_signal_catalogues()  # M1/M3 catalogues (analytics-m1-m3): a bad YAML stops startup, not a document
        store = PostgresStore(worker_settings.database_url, max_document_bytes=worker_settings.max_document_bytes)
    except (ConfigError, StoreMisconfigured) as exc:
        log.error("worker not started", extra={"reason": "config_error", "error": str(exc)})
        return 2
    except (RegistryError, CatalogueError, OSError) as exc:
        log.error("worker not started", extra={"reason": "config_error", "error": f"REGISTRY_CSV / catalogue: {exc}"})
        return 2
    try:
        client = stream_client(worker_settings.redis_url, worker_settings.stream_block_ms)
    except ValueError:
        store.close()
        log.error("worker not started", extra={"reason": "config_error", "error": "REDIS_URL is malformed"})
        return 2
    worker = Worker(client, store, RedisPublisher(client), registry=registry, catalogue=catalogue,
                    judge=build_judge(llm_settings, redis=client),
                    config=WorkerConfig(consumer=worker_settings.consumer,
                                        block_ms=worker_settings.stream_block_ms,
                                        claim_min_idle_ms=worker_settings.claim_min_idle_ms,
                                        max_deliveries=worker_settings.max_deliveries))
    install_signal_handlers(worker)
    # /health has its own short-timeout clients, so a slow dependency never blocks the HTTP thread or the loop.
    health_redis = redis.Redis.from_url(worker_settings.redis_url, socket_timeout=1, socket_connect_timeout=1)
    health_store = PostgresStore(worker_settings.database_url, connect_timeout=1)
    try:
        health = start_health_server(worker_settings.health_port,
                                     {"redis": lambda: bool(health_redis.ping()), "db": health_store.ping})
    except OSError as exc:  # port taken or not allowed
        log.error("worker not started", extra={"reason": "config_error",
                                               "error": f"HEALTH_PORT {worker_settings.health_port}: {exc.strerror}"})
        for closable in (health_redis, health_store, store, client):
            closable.close()
        return 2
    log.info("worker starting", extra={"consumer": worker_settings.consumer, "stream": STREAM, "group": GROUP,
                                       "health_port": worker_settings.health_port})
    try:
        worker.ensure_group()
        worker.run()
    except StoreMisconfigured as exc:
        log.error("worker stopped", extra={"reason": "config_error", "error": str(exc)})
        return 2
    finally:
        health.shutdown()
        health_store.close()
        health_redis.close()
        store.close()
        client.close()
    log.info("worker stopped", extra={"reason": "signal"})
    return 0


if __name__ == "__main__":
    sys.exit(main())
