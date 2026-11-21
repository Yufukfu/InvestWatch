"""document-stream-worker scenarios (openspec/specs/document-stream-worker/spec.md).

fakeredis + InMemoryStore + NoopPublisher; one test against real Redis runs with TEST_REDIS_URL.
"""

from __future__ import annotations

import logging
import os
import uuid

import fakeredis
import pytest
import redis

from conftest import NOW, make_doc, redis_test_url
from investwatch_analytics.registry import Registry
from investwatch_analytics.config import Settings
from investwatch_analytics.rules.engine import Catalogue
from investwatch_analytics.storage import StoreError, StoreMisconfigured, StoreUnavailable
from investwatch_analytics.testing import InMemoryStore, NoopPublisher
from investwatch_analytics.worker import (
    GROUP,
    STREAM,
    StopRequested,
    Worker,
    WorkerConfig,
    install_signal_handlers,
    main,
    stream_client,
)

DOC_ID = "22222222-2222-4222-8222-222222222222"
DOC2_ID = "33333333-3333-4333-8333-333333333333"
MISSING_ID = "99999999-9999-4999-8999-999999999999"


@pytest.fixture(scope="module")
def registry():
    return Registry.from_csv(Settings.from_env().registry_csv)


@pytest.fixture(scope="module")
def catalogue():
    return Catalogue.load()


@pytest.fixture
def r():
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def store():
    s = InMemoryStore()
    s.put_document_row(make_doc(id=DOC_ID, text="Reklama. Alfa Inwestycje. Zarabiaj 18% rocznie!"))
    s.put_document_row(make_doc(id=DOC2_ID, text="Reklama. Przykładowy tekst."))
    return s


class Recorder(NoopPublisher):
    """NoopPublisher that also records the order of side effects relative to XACK."""

    def __init__(self, journal: list[str] | None = None, **kw) -> None:
        super().__init__(**kw)
        self.journal = journal if journal is not None else []

    def publish_findings(self, saved):
        self.journal.append("publish")
        return super().publish_findings(saved)


def make_worker(r, store, registry, catalogue, *, publisher=None, consumer="w1", stream=STREAM, **cfg) -> Worker:
    config = WorkerConfig(consumer=consumer, block_ms=10, claim_min_idle_ms=cfg.pop("claim_min_idle_ms", 60000),
                          max_deliveries=cfg.pop("max_deliveries", 5), stream=stream)
    return Worker(r, store, publisher or Recorder(), registry=registry, catalogue=catalogue, config=config,
                  now=lambda: NOW, sleep=lambda s: None, jitter=lambda: 0.0)


def xadd(r, document_id=DOC_ID, schema="v1", **extra) -> str:
    fields = {"document_id": document_id, "schema": schema, **extra}
    return r.xadd(STREAM, {k: v for k, v in fields.items() if v is not None})


def pending(r) -> int:
    return r.xpending(STREAM, GROUP)["pending"]


def outcomes(caplog) -> list[str]:
    return [rec.outcome for rec in caplog.records if hasattr(rec, "outcome")]


# ---- consumer group ----------------------------------------------------------------------------


def test_first_start_creates_stream_and_group(r, store, registry, catalogue):
    w = make_worker(r, store, registry, catalogue)
    w.ensure_group()
    assert r.exists(STREAM)
    assert [g["name"] for g in r.xinfo_groups(STREAM)] == [GROUP]


def test_existing_group_is_kept(r, store, registry, catalogue):
    w = make_worker(r, store, registry, catalogue)
    w.ensure_group()
    xadd(r)
    w.run_once()
    last = r.xinfo_groups(STREAM)[0]["last-delivered-id"]
    w.ensure_group()  # BUSYGROUP is success
    assert r.xinfo_groups(STREAM)[0]["last-delivered-id"] == last


def test_backlog_from_before_the_group_is_processed(r, store, registry, catalogue):
    xadd(r)  # the scraper published before analytics ever started
    w = make_worker(r, store, registry, catalogue)
    w.ensure_group()
    w.run_once()
    assert len(store.findings_for_document(DOC_ID)) == 1


# ---- happy path and ordering --------------------------------------------------------------------


def test_happy_path_commit_then_publish_then_ack(r, store, registry, catalogue, caplog):
    journal: list[str] = []
    publisher = Recorder(journal)
    w = make_worker(r, store, registry, catalogue, publisher=publisher)
    w.ensure_group()
    original_save, original_ack = store.save_findings, r.xack

    def save(doc, findings):
        journal.append("commit")
        return original_save(doc, findings)

    def ack(*args):
        journal.append("ack")
        return original_ack(*args)

    store.save_findings, r.xack = save, ack
    xadd(r)
    with caplog.at_level(logging.INFO):
        assert w.run_once() == 1
    assert journal == ["commit", "publish", "ack"]
    [f] = store.findings_for_document(DOC_ID)
    assert f.module == "M2" and f.model.llm is None and f.model.pipeline_version
    assert [e["type"] for e in publisher.sent][0] == "finding.created"
    assert pending(r) == 0
    [rec] = [rec for rec in caplog.records if hasattr(rec, "outcome")]
    assert (rec.outcome, rec.document_id, rec.findings_created, rec.findings_updated) == ("stored", DOC_ID, 1, 0)
    assert rec.stream_id and isinstance(rec.duration_ms, (int, float))


def test_no_findings_is_acked_without_store_or_publish(r, store, registry, catalogue, caplog):
    store.put_document_row(make_doc(id=DOC_ID, source_kind="third_party"))
    publisher = Recorder()
    w = make_worker(r, store, registry, catalogue, publisher=publisher)
    w.ensure_group()
    xadd(r)
    with caplog.at_level(logging.INFO):
        w.run_once()
    assert store.findings_for_document(DOC_ID) == [] and publisher.journal == [] and pending(r) == 0
    assert outcomes(caplog) == ["no_findings"]


# ---- duplicates ---------------------------------------------------------------------------------


def test_same_message_twice_is_idempotent(r, store, registry, catalogue, caplog):
    publisher = Recorder()
    w = make_worker(r, store, registry, catalogue, publisher=publisher)
    w.ensure_group()
    xadd(r)
    xadd(r)  # republish sweep / manual re-XADD of the same document
    with caplog.at_level(logging.INFO):
        w.run_once()
        w.run_once()
    [f] = store.findings_for_document(DOC_ID)
    assert [e["type"] for e in publisher.sent].count("finding.created") == 1
    assert pending(r) == 0
    second = [rec for rec in caplog.records if hasattr(rec, "outcome")][1]
    assert (second.outcome, second.findings_created, second.findings_updated) == ("stored", 0, 1)


def test_two_consumers_same_document(r, store, registry, catalogue):
    publisher = Recorder()
    a = make_worker(r, store, registry, catalogue, publisher=publisher, consumer="a")
    b = make_worker(r, store, registry, catalogue, publisher=publisher, consumer="b")
    a.ensure_group()
    xadd(r)
    xadd(r)
    a.run_once()
    b.run_once()
    assert len(store.findings_for_document(DOC_ID)) == 1
    assert [e["type"] for e in publisher.sent].count("finding.created") == 1


class Crash(BaseException):
    """Simulates the process dying (not an Exception, so nothing in the worker may swallow it)."""


def test_crash_between_commit_and_ack_is_redelivered_without_new_events(r, store, registry, catalogue):
    publisher = Recorder()
    dying = make_worker(r, store, registry, catalogue, publisher=publisher, consumer="dying")
    dying.ensure_group()
    xadd(r)

    def die(*args):
        raise Crash

    r.xack, real_ack = die, r.xack
    with pytest.raises(Crash):
        dying.run_once()
    r.xack = real_ack
    assert pending(r) == 1 and len(store.findings_for_document(DOC_ID)) == 1
    sent_before = len(publisher.sent)
    survivor = make_worker(r, store, registry, catalogue, publisher=publisher, consumer="survivor", claim_min_idle_ms=0)
    survivor.run_once()
    assert pending(r) == 0
    assert len(publisher.sent) == sent_before  # the redelivery is an update: no new event
    assert len(store.findings_for_document(DOC_ID)) == 1


def test_reanalysis_after_rule_change_updates_in_place(r, store, registry, catalogue):
    w = make_worker(r, store, registry, catalogue)
    w.ensure_group()
    xadd(r)
    w.run_once()
    [before] = store.findings_for_document(DOC_ID)
    store.set_review(DOC_ID, "M2", status="confirmed", note="ok")
    xadd(r)
    w.run_once()
    [after] = store.findings_for_document(DOC_ID)
    assert (after.id, after.status, after.note) == (before.id, "confirmed", "ok")


# ---- poison messages ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fields",
    [
        {"schema": "v1"},
        {"document_id": "not-a-uuid", "schema": "v1"},
        {"document_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa".upper(), "schema": "v1"},  # contract: lowercase
        {"document_id": DOC_ID, "schema": "v2"},
        {"document_id": DOC_ID},
        {"document_id": DOC_ID, "schema": "v1", "extra": "x"},
    ],
    ids=["no-id", "not-uuid", "uppercase-uuid", "schema-v2", "no-schema", "extra-field"],
)
def test_malformed_message_is_acked_as_invalid_message(r, store, registry, catalogue, caplog, fields):
    publisher = Recorder()
    w = make_worker(r, store, registry, catalogue, publisher=publisher)
    w.ensure_group()
    r.xadd(STREAM, fields)
    with caplog.at_level(logging.WARNING):
        w.run_once()
    assert pending(r) == 0 and publisher.journal == [] and store.findings_for_document(DOC_ID) == []
    [rec] = [rec for rec in caplog.records if hasattr(rec, "outcome")]
    assert rec.outcome == "invalid_message" and rec.levelno == logging.WARNING and rec.stream_id
    valid_id = fields.get("document_id") == DOC_ID
    assert getattr(rec, "document_id", None) == (DOC_ID if valid_id else None)  # logged only when it is a UUID


def test_missing_document_is_acked(r, store, registry, catalogue, caplog):
    w = make_worker(r, store, registry, catalogue)
    w.ensure_group()
    xadd(r, MISSING_ID)
    with caplog.at_level(logging.WARNING):
        w.run_once()
    assert pending(r) == 0
    [rec] = [rec for rec in caplog.records if hasattr(rec, "outcome")]
    assert (rec.outcome, rec.document_id, rec.levelno) == ("document_not_found", MISSING_ID, logging.WARNING)


def test_invalid_document_is_acked_naming_the_field(r, store, registry, catalogue, caplog):
    store.put_document_row(make_doc(id=DOC_ID, url="ftp://example.com/x"))
    w = make_worker(r, store, registry, catalogue)
    w.ensure_group()
    xadd(r)
    with caplog.at_level(logging.WARNING):
        w.run_once()
    assert pending(r) == 0
    [rec] = [rec for rec in caplog.records if hasattr(rec, "outcome")]
    assert (rec.outcome, rec.field) == ("invalid_document", "url")


def test_poison_does_not_stop_the_loop(r, store, registry, catalogue):
    w = make_worker(r, store, registry, catalogue)
    w.ensure_group()
    r.xadd(STREAM, {"schema": "v1"})
    xadd(r)
    w.run_once()
    w.run_once()
    assert len(store.findings_for_document(DOC_ID)) == 1 and pending(r) == 0


def test_pipeline_bug_retries_until_max_deliveries(r, store, registry, catalogue, caplog, monkeypatch):
    import investwatch_analytics.worker as worker_mod

    def boom(*args, **kwargs):
        raise RuntimeError("pipeline bug")

    monkeypatch.setattr(worker_mod, "analyze", boom)
    w = make_worker(r, store, registry, catalogue, max_deliveries=3, claim_min_idle_ms=0)
    w.ensure_group()
    xadd(r)
    with caplog.at_level(logging.INFO):
        w.run_once()  # delivery 1
        assert pending(r) == 1
        w.run_once()  # delivery 2 (claimed)
        assert pending(r) == 1
        w.run_once()  # delivery 3 = MAX_DELIVERIES: acked
    assert pending(r) == 0
    assert outcomes(caplog) == ["retry_later", "retry_later", "max_deliveries_exceeded"]
    final = [rec for rec in caplog.records if getattr(rec, "outcome", None) == "max_deliveries_exceeded"][0]
    assert final.levelno == logging.ERROR and final.exc_info and final.deliveries == 3


def test_unexpected_store_error_counts_toward_max_deliveries(r, store, registry, catalogue, caplog):
    def fk(doc, findings):
        raise StoreError("ForeignKeyViolation (sqlstate 23503)")

    store.save_findings = fk
    w = make_worker(r, store, registry, catalogue, max_deliveries=1)
    w.ensure_group()
    xadd(r)
    with caplog.at_level(logging.INFO):
        w.run_once()
    assert pending(r) == 0 and outcomes(caplog) == ["max_deliveries_exceeded"]


def test_non_redis_publish_error_is_logged_and_acked(r, store, registry, catalogue, caplog):
    class Broken(NoopPublisher):
        def publish_findings(self, saved):
            raise TypeError("odd client")

    w = make_worker(r, store, registry, catalogue, publisher=Broken())
    w.ensure_group()
    xadd(r)
    with caplog.at_level(logging.INFO):
        w.run_once()
    assert pending(r) == 0 and len(store.findings_for_document(DOC_ID)) == 1
    assert any(getattr(rec, "reason", None) == "publish_failed" for rec in caplog.records)


# ---- reclaim ------------------------------------------------------------------------------------


def test_dead_consumer_message_is_claimed_when_stale(r, store, registry, catalogue):
    a = make_worker(r, store, registry, catalogue, consumer="a")
    a.ensure_group()
    xadd(r)
    r.xreadgroup(GROUP, "a", {STREAM: ">"}, count=1)  # a reads and dies
    b = make_worker(r, store, registry, catalogue, consumer="b", claim_min_idle_ms=0)
    b.run_once()
    assert pending(r) == 0 and len(store.findings_for_document(DOC_ID)) == 1


def test_fresh_pending_message_is_not_claimed(r, store, registry, catalogue):
    a = make_worker(r, store, registry, catalogue, consumer="a")
    a.ensure_group()
    xadd(r)
    r.xreadgroup(GROUP, "a", {STREAM: ">"}, count=1)
    b = make_worker(r, store, registry, catalogue, consumer="b", claim_min_idle_ms=3_600_000)
    b.run_once()
    assert pending(r) == 1 and store.findings_for_document(DOC_ID) == []


# ---- outages ------------------------------------------------------------------------------------


def test_store_outage_leaves_pending_then_succeeds(r, store, registry, catalogue, caplog):
    sleeps: list[float] = []
    w = make_worker(r, store, registry, catalogue, claim_min_idle_ms=0)
    w._sleep = sleeps.append
    w.ensure_group()
    xadd(r)
    store.unavailable = True
    with caplog.at_level(logging.WARNING):
        w.run(max_iterations=3)
    assert pending(r) == 1 and sleeps == [1, 2, 4]
    assert [rec.reason for rec in caplog.records if hasattr(rec, "reason")] == ["db_unavailable"] * 3
    store.unavailable = False
    w.run(max_iterations=1)
    assert pending(r) == 0 and len(store.findings_for_document(DOC_ID)) == 1


def test_backoff_is_capped_and_resets(r, store, registry, catalogue):
    sleeps: list[float] = []
    w = make_worker(r, store, registry, catalogue, claim_min_idle_ms=0)
    w._sleep = sleeps.append
    w.ensure_group()
    xadd(r)
    store.unavailable = True
    w.run(max_iterations=7)
    assert sleeps == [1, 2, 4, 8, 16, 30, 30]
    store.unavailable = False
    w.run(max_iterations=1)
    store.unavailable = True
    xadd(r, DOC2_ID)
    sleeps.clear()
    w.run(max_iterations=1)
    assert sleeps == [1]


def test_backoff_adds_jitter(r, store, registry, catalogue):
    sleeps: list[float] = []
    w = make_worker(r, store, registry, catalogue, claim_min_idle_ms=0)
    w._sleep, w._jitter = sleeps.append, lambda: 0.25
    w.ensure_group()
    xadd(r)
    store.unavailable = True
    w.run(max_iterations=1)
    assert sleeps == [1.25]


class FlakyRedis(fakeredis.FakeRedis):
    """The next `failures` stream calls (XAUTOCLAIM or XREADGROUP) raise a connection error."""

    failures = 0

    def _maybe_fail(self) -> None:
        if self.failures > 0:
            self.failures -= 1
            raise redis.ConnectionError("down")

    def xreadgroup(self, *args, **kwargs):
        self._maybe_fail()
        return super().xreadgroup(*args, **kwargs)

    def xautoclaim(self, *args, **kwargs):
        self._maybe_fail()
        return super().xautoclaim(*args, **kwargs)


def test_redis_outage_backs_off_without_exiting(store, registry, catalogue, caplog):
    fr = FlakyRedis(decode_responses=True)
    sleeps: list[float] = []
    w = make_worker(fr, store, registry, catalogue)
    w._sleep = sleeps.append
    w.ensure_group()
    xadd(fr)
    fr.failures = 2
    with caplog.at_level(logging.WARNING):
        w.run(max_iterations=3)
    assert sleeps == [1, 2]
    assert [rec.reason for rec in caplog.records if hasattr(rec, "reason")] == ["redis_unavailable"] * 2
    assert len(store.findings_for_document(DOC_ID)) == 1


def test_misconfigured_store_stops_the_loop(r, store, registry, catalogue):
    def bad(document_id):
        raise StoreMisconfigured("DATABASE_URL is malformed")

    store.load_document = bad
    w = make_worker(r, store, registry, catalogue)
    w.ensure_group()
    xadd(r)
    with pytest.raises(StoreMisconfigured):
        w.run(max_iterations=5)
    assert pending(r) == 1


def test_group_creation_retries_while_redis_is_down(store, registry, catalogue):
    class DownThenUp(fakeredis.FakeRedis):
        failures = 2

        def xgroup_create(self, *args, **kwargs):
            if self.failures:
                self.failures -= 1
                raise redis.ConnectionError("down")
            return super().xgroup_create(*args, **kwargs)

    dr = DownThenUp(decode_responses=True)
    sleeps: list[float] = []
    w = make_worker(dr, store, registry, catalogue)
    w._sleep = sleeps.append
    w.ensure_group()
    assert sleeps == [1, 2] and dr.xinfo_groups(STREAM)


# ---- stop ---------------------------------------------------------------------------------------


def test_stop_finishes_the_current_message_and_reads_no_more(r, store, registry, catalogue):
    class StopDuring(Recorder):
        def publish_findings(self, saved):
            worker.request_stop()
            return super().publish_findings(saved)

    worker = make_worker(r, store, registry, catalogue, publisher=StopDuring())
    worker.ensure_group()
    xadd(r)
    xadd(r, DOC2_ID)
    worker.run(max_iterations=10)
    assert pending(r) == 0  # the current one was acked
    assert store.findings_for_document(DOC2_ID) == []  # the next one was never read...
    [[_, unread]] = r.xreadgroup(GROUP, "other", {STREAM: ">"}, count=5)
    assert [fields["document_id"] for _, fields in unread] == [DOC2_ID]  # ...so it is still undelivered


# ---- main ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("missing", ["DATABASE_URL", "REDIS_URL"])
def test_main_exits_non_zero_naming_the_missing_variable(missing, capsys):
    env = {"DATABASE_URL": "postgresql://u@127.0.0.1:1/db", "REDIS_URL": "redis://127.0.0.1:1/0"}
    del env[missing]
    assert main(env) == 2
    assert missing in capsys.readouterr().out


def test_main_exits_non_zero_on_malformed_database_url(capsys):
    assert main({"DATABASE_URL": "postgresql://u:pw%zz@h/db", "REDIS_URL": "redis://127.0.0.1:1/0"}) == 2
    out = capsys.readouterr().out
    assert "DATABASE_URL is malformed" in out and "pw%zz" not in out


def test_main_exits_non_zero_on_bad_registry(tmp_path, capsys):
    bad = tmp_path / "r.csv"
    bad.write_text("nope\n", encoding="utf-8")
    env = {"DATABASE_URL": "postgresql://u@127.0.0.1:1/db", "REDIS_URL": "redis://127.0.0.1:1/0",
           "REGISTRY_CSV": str(bad)}
    assert main(env) == 2
    out = capsys.readouterr().out
    assert "r.csv" in out and "config_error" in out  # names the file, not just the fixed prefix


# ---- real Redis ---------------------------------------------------------------------------------


@pytest.mark.skipif(not redis_test_url(), reason="TEST_REDIS_URL / IW_TEST_REDIS_URL not set")
def test_real_redis_autoclaim_and_delivery_count(store, registry, catalogue, caplog):
    real = redis.Redis.from_url(redis_test_url(), decode_responses=True)
    stream = f"{STREAM}:test:{uuid.uuid4().hex[:8]}"
    try:
        w = make_worker(real, store, registry, catalogue, consumer="a", max_deliveries=3, claim_min_idle_ms=0,
                        stream=stream)
        w.ensure_group()
        real.xadd(stream, {"document_id": DOC_ID, "schema": "v1"})
        real.xreadgroup(GROUP, "dead", {stream: ">"}, count=1)  # delivery 1 by a consumer that dies
        import investwatch_analytics.worker as worker_mod

        real_analyze = worker_mod.analyze
        worker_mod.analyze = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("bug"))
        try:
            with caplog.at_level(logging.INFO):
                w.run_once()  # claimed: delivery 2 < 3 -> retry_later
                assert real.xpending(stream, GROUP)["pending"] == 1
                w.run_once()  # claimed: delivery 3 -> max_deliveries_exceeded, acked
        finally:
            worker_mod.analyze = real_analyze
        assert real.xpending(stream, GROUP)["pending"] == 0
        assert [(rec.outcome, rec.deliveries) for rec in caplog.records if hasattr(rec, "deliveries")] == [
            ("retry_later", 2), ("max_deliveries_exceeded", 3)]
        real.xadd(stream, {"document_id": DOC_ID, "schema": "v1"})
        w.run_once()  # a healthy message on real Redis: XREADGROUP, save, XACK
        assert real.xpending(stream, GROUP)["pending"] == 0
        assert len(store.findings_for_document(DOC_ID)) == 1
    finally:
        real.delete(stream)


def test_store_outage_during_save_leaves_the_message_pending(r, store, registry, catalogue, caplog):
    def down(doc, findings):
        raise StoreUnavailable("connection lost mid-save")

    store.save_findings = down
    sleeps: list[float] = []
    w = make_worker(r, store, registry, catalogue, max_deliveries=1)
    w._sleep = sleeps.append
    w.ensure_group()
    xadd(r)
    with caplog.at_level(logging.WARNING):
        w.run(max_iterations=1)
    assert pending(r) == 1 and sleeps == [1]  # retryable: not acked even at MAX_DELIVERIES
    assert [rec.reason for rec in caplog.records if hasattr(rec, "reason")] == ["db_unavailable"]


def test_stopped_worker_makes_no_more_redis_calls(r, store, registry, catalogue):
    calls: list[str] = []

    class Counting(fakeredis.FakeRedis):
        def xautoclaim(self, *a, **k):
            calls.append("xautoclaim")
            return super().xautoclaim(*a, **k)

        def xreadgroup(self, *a, **k):
            calls.append("xreadgroup")
            return super().xreadgroup(*a, **k)

    cr = Counting(decode_responses=True)
    w = make_worker(cr, store, registry, catalogue)
    w.ensure_group()
    w.request_stop()
    w.run(max_iterations=10)
    assert calls == []


def test_stop_cuts_a_backoff_short(r, store, registry, catalogue):
    import threading
    import time as _time

    w = Worker(r, store, Recorder(), registry=registry, catalogue=catalogue,
               config=WorkerConfig(consumer="w1", block_ms=10, claim_min_idle_ms=0), now=lambda: NOW,
               jitter=lambda: 0.0)  # default sleep: the stop event
    w.ensure_group()
    xadd(r)
    store.unavailable = True
    w._backoff = 30
    threading.Timer(0.2, w.request_stop).start()
    started = _time.monotonic()
    w.run()
    assert _time.monotonic() - started < 5  # not the 30 s backoff
    assert pending(r) == 1


def test_main_exits_non_zero_on_malformed_redis_url(capsys):
    env = {"DATABASE_URL": "postgresql://u@127.0.0.1:1/db", "REDIS_URL": "nope://:s3cret@redis:6379/0"}
    assert main(env) == 2
    out = capsys.readouterr().out
    assert "REDIS_URL is malformed" in out and "s3cret" not in out


def test_nogroup_recreates_the_group(r, store, registry, catalogue, caplog):
    w = make_worker(r, store, registry, catalogue)
    w.ensure_group()
    r.delete(STREAM)  # stream and group gone (FLUSHALL, manual cleanup)
    with caplog.at_level(logging.WARNING):
        w.run(max_iterations=1)
    assert [g["name"] for g in r.xinfo_groups(STREAM)] == [GROUP]
    assert any(getattr(rec, "reason", None) == "group_missing" for rec in caplog.records)
    xadd(r)
    w.run(max_iterations=1)
    assert len(store.findings_for_document(DOC_ID)) == 1


def test_other_redis_response_error_backs_off(store, registry, catalogue, caplog):
    class ReadOnly(fakeredis.FakeRedis):
        def xautoclaim(self, *a, **k):
            raise redis.ResponseError("READONLY You can't write against a read only replica.")

    sleeps: list[float] = []
    ro = ReadOnly(decode_responses=True)
    w = make_worker(ro, store, registry, catalogue)
    w._sleep = sleeps.append
    w.ensure_group()
    with caplog.at_level(logging.WARNING):
        w.run(max_iterations=2)
    assert sleeps == [1, 2]


def test_signal_during_the_idle_read_leaves_at_once(store, registry, catalogue):
    holder: dict = {}

    class SignalWhileBlocked(fakeredis.FakeRedis):
        def xreadgroup(self, *a, **k):
            holder["worker"].handle_signal()  # SIGTERM arrives while blocked in the read
            raise AssertionError("not reached: the handler raises inside the blocking call")

    sr = SignalWhileBlocked(decode_responses=True)
    w = make_worker(sr, store, registry, catalogue)
    holder["worker"] = w
    w.ensure_group()
    w.run(max_iterations=10)  # returns, does not raise
    assert w._stop and not w._idle_read


def test_signal_while_processing_finishes_the_message(r, store, registry, catalogue):
    class SignalDuringPublish(Recorder):
        def publish_findings(self, saved):
            worker.handle_signal()  # not idle: must not raise, only set the flag
            return super().publish_findings(saved)

    worker = make_worker(r, store, registry, catalogue, publisher=SignalDuringPublish())
    worker.ensure_group()
    xadd(r)
    worker.run(max_iterations=10)
    assert pending(r) == 0 and len(store.findings_for_document(DOC_ID)) == 1


def test_installed_handlers_route_signals_to_the_worker(r, store, registry, catalogue):
    import signal

    w = make_worker(r, store, registry, catalogue)
    saved = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGINT)}
    try:
        install_signal_handlers(w)
        w._idle_read = True
        with pytest.raises(StopRequested):
            signal.raise_signal(signal.SIGINT)
        assert w._stop
        w._idle_read = False
        w._stop = False
        signal.raise_signal(signal.SIGTERM)  # not idle: no exception, only the flag
        assert w._stop
    finally:
        for sig, handler in saved.items():
            signal.signal(sig, handler)


def test_second_signal_never_raises(r, store, registry, catalogue):
    w = make_worker(r, store, registry, catalogue)
    w._idle_read = True
    with pytest.raises(StopRequested):
        w.handle_signal()
    w.handle_signal()  # e.g. a second SIGTERM during cleanup, flag still set: no exception
    assert w._stop


def test_main_exits_2_when_the_health_port_is_taken(capsys, monkeypatch):
    import socket

    import investwatch_analytics.worker as worker_mod

    class NoConnect:
        def __init__(self, *a, **k):
            pass

        def close(self):
            pass

        def ping(self):
            return False

    monkeypatch.setattr(worker_mod.redis.Redis, "from_url", classmethod(lambda cls, *a, **k: NoConnect()))
    with socket.socket() as taken:
        taken.bind(("0.0.0.0", 0))
        taken.listen()
        port = taken.getsockname()[1]
        env = {"DATABASE_URL": "postgresql://u@127.0.0.1:1/db", "REDIS_URL": "redis://127.0.0.1:1/0",
               "HEALTH_PORT": str(port)}
        assert main(env) == 2
    out = capsys.readouterr().out
    assert "HEALTH_PORT" in out and "config_error" in out


def test_non_utf8_message_is_acked_as_invalid_not_a_crash(store, registry, catalogue, caplog):
    server = fakeredis.FakeServer()
    raw = fakeredis.FakeRedis(server=server)  # a writer that sends raw bytes
    worker_client = fakeredis.FakeRedis(server=server, decode_responses=True, encoding_errors="replace")
    w = make_worker(worker_client, store, registry, catalogue)
    w.ensure_group()
    raw.xadd(STREAM, {b"document_id": b"\xff\xfe\xfd", b"schema": b"v1"})
    xadd(worker_client)  # a valid message behind it
    with caplog.at_level(logging.INFO):
        w.run(max_iterations=2)
    assert outcomes(caplog) == ["invalid_message", "stored"]
    assert worker_client.xpending(STREAM, GROUP)["pending"] == 0


def test_stream_client_replaces_undecodable_bytes():
    client = stream_client("redis://127.0.0.1:1/0", 5000)
    kwargs = client.connection_pool.connection_kwargs
    assert kwargs["decode_responses"] is True and kwargs["encoding_errors"] == "replace"
    assert kwargs["socket_timeout"] == 10  # longer than the 5 s block, so a blocking read never times out early
    client.close()


def test_unforeseen_error_in_the_loop_backs_off_instead_of_crashing(store, registry, catalogue, caplog):
    class Odd(fakeredis.FakeRedis):
        calls = 0

        def xautoclaim(self, *a, **k):
            self.calls += 1
            if self.calls == 1:
                raise ValueError("something nobody planned for")
            return super().xautoclaim(*a, **k)

    odd = Odd(decode_responses=True)
    sleeps: list[float] = []
    w = make_worker(odd, store, registry, catalogue)
    w._sleep = sleeps.append
    w.ensure_group()
    xadd(odd)
    with caplog.at_level(logging.WARNING):
        w.run(max_iterations=2)
    assert sleeps == [1]
    assert any(getattr(rec, "reason", None) == "unexpected_error" and rec.exc_info for rec in caplog.records)
    assert len(store.findings_for_document(DOC_ID)) == 1  # the loop carried on


def test_oversized_document_is_acked_as_invalid(r, registry, catalogue, caplog):
    store = InMemoryStore(max_document_bytes=1_000)
    store.put_document_row(make_doc(id=DOC_ID, text="Reklama. " + "z" * 5_000))
    w = make_worker(r, store, registry, catalogue)
    w.ensure_group()
    xadd(r)
    with caplog.at_level(logging.WARNING):
        w.run_once()
    assert pending(r) == 0
    [rec] = [rec for rec in caplog.records if hasattr(rec, "outcome")]
    assert (rec.outcome, rec.field) == ("invalid_document", "text")


def test_main_exits_non_zero_on_bad_signal_catalogue(tmp_path, capsys, monkeypatch):
    from investwatch_analytics import pipeline
    from investwatch_analytics.rules import engine

    bad = tmp_path / "m3.yaml"
    bad.write_text("bias: 0\nrules:\n  - {id: S1.1, name: x, severity: low, weight: 1}\n", encoding="utf-8")
    monkeypatch.setitem(engine.MODULE_CATALOGUES, "M3", bad)
    pipeline.default_signal_catalogues.cache_clear()
    import investwatch_analytics.worker as worker_module

    def no_redis(*args, **kwargs):  # never reach the network: a missed check must fail fast, not retry forever
        raise ValueError("stub")

    monkeypatch.setattr(worker_module, "stream_client", no_redis)
    try:
        env = {"DATABASE_URL": "postgresql://u@127.0.0.1:1/db", "REDIS_URL": "redis://127.0.0.1:1/0"}
        assert main(env) == 2
        out = capsys.readouterr().out
        assert "m3.yaml" in out and "config_error" in out
    finally:
        pipeline.default_signal_catalogues.cache_clear()


def test_document_with_m1_and_m3_findings(r, store, registry, catalogue, caplog):
    """analytics-m1-m3: one document, two modules -> two rows, two finding.created events, one ack."""
    doc3 = "33333333-3333-4333-8333-333333333333"
    store.put_document_row(make_doc(
        id=doc3, source_kind="third_party", platform="instagram", url="https://www.instagram.com/p/W1/",
        author={"handle": "@trader_ola"},
        text="Konto mam w EuroTrade Markets. Moja grupa: co tydzień mówię, co kupić z akcji WIG20.",
    ))
    publisher = Recorder()
    w = make_worker(r, store, registry, catalogue, publisher=publisher)
    w.ensure_group()
    xadd(r, document_id=doc3)
    with caplog.at_level(logging.INFO):
        w.run_once()
    assert sorted(f.module for f in store.findings_for_document(doc3)) == ["M1", "M3"]
    created = [e["data"]["module"] for e in publisher.sent if e["type"] == "finding.created"]
    assert sorted(created) == ["M1", "M3"] and pending(r) == 0
    rec = next(rec for rec in caplog.records if getattr(rec, "outcome", None) == "stored")
    assert rec.findings_created == 2
