"""finding-events scenarios (openspec/specs/finding-events/spec.md), on fakeredis."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import fakeredis
import pytest
import redis

from conftest import NOW
from investwatch_analytics.events import (
    DEFAULT_THRESHOLDS,
    EVENTS_CHANNEL,
    THRESHOLDS_KEY,
    RedisPublisher,
    read_thresholds,
)
from investwatch_analytics.models import Finding
from investwatch_analytics.storage import SavedFinding
from investwatch_analytics.testing import NoopPublisher

EMITTED = datetime(2026, 11, 21, 16, 30, tzinfo=timezone.utc)


def clock() -> datetime:
    return EMITTED


def finding(module: str = "M2", score: float = 0.3, fid: str = "44444444-4444-4444-8444-444444444444") -> Finding:
    return Finding(
        id=fid,
        document_id="22222222-2222-4222-8222-222222222222",
        module=module,
        score=score,
        title="Brak oznaczenia reklamy",
        rules=[],
        url="https://example.com/oferta",
        platform="web",
        detected_at=NOW,
        updated_at=NOW,
    )


def created(**kw) -> SavedFinding:
    return SavedFinding(finding(**kw), "created")


class CountingRedis(fakeredis.FakeRedis):
    """Counts real GETs of the thresholds key, so a cache anywhere in the publisher is visible."""

    threshold_gets = 0

    def get(self, name):
        if name == THRESHOLDS_KEY:
            self.threshold_gets += 1
        return super().get(name)


@pytest.fixture
def r():
    return CountingRedis(decode_responses=True)


@pytest.fixture
def sub(r):
    ps = r.pubsub()
    ps.subscribe(EVENTS_CHANNEL)
    ps.get_message(timeout=1)  # subscribe confirmation

    def received() -> list[dict]:
        out = []
        while (msg := ps.get_message(timeout=0.05)) is not None:
            out.append(json.loads(msg["data"]))
        return out

    return received


def set_thresholds(r, **values) -> None:
    r.set(THRESHOLDS_KEY, json.dumps({**DEFAULT_THRESHOLDS, **values}))


# ---- envelope -----------------------------------------------------------------------------------


def test_created_event_shape(r, sub):
    RedisPublisher(r, clock=clock).publish_findings([created()])
    [event] = sub()
    assert event == {
        "type": "finding.created",
        "emitted_at": "2026-11-21T16:30:00Z",
        "data": {
            "id": "44444444-4444-4444-8444-444444444444",
            "module": "M2",
            "score": 0.3,
            "title": "Brak oznaczenia reklamy",
            "url": "https://example.com/oferta",
            "platform": "web",
        },
    }


def test_events_validate_against_contract(r, sub, contracts_dir):
    from jsonschema import Draft202012Validator, FormatChecker

    schema = json.loads((contracts_dir / "schemas" / "events.schema.json").read_text(encoding="utf-8"))
    # the whole schema (its oneOf), as the API's Socket.IO relay validates it: a message matching two branches is dropped too
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    RedisPublisher(r, clock=clock).publish_findings([created(score=0.9), created(module="M1", score=0.1)])
    events = sub()
    assert len(events) == 3
    for event in events:
        assert list(validator.iter_errors(event)) == []
        assert "risk_level" not in event["data"]


def test_event_id_comes_from_the_save_result(r, sub):
    stored = finding(fid="55555555-5555-4555-8555-555555555555")
    RedisPublisher(r, clock=clock).publish_findings([SavedFinding(stored, "created")])
    assert sub()[0]["data"]["id"] == "55555555-5555-4555-8555-555555555555"


# ---- which events -------------------------------------------------------------------------------


def test_low_score_only_created(r, sub):
    set_thresholds(r, M2=0.5)
    RedisPublisher(r, clock=clock).publish_findings([created(score=0.3)])
    assert [e["type"] for e in sub()] == ["finding.created"]


def test_score_equal_to_threshold_is_high_risk(r, sub):
    set_thresholds(r, M2=0.5)
    RedisPublisher(r, clock=clock).publish_findings([created(score=0.5)])
    events = sub()
    assert [e["type"] for e in events] == ["finding.created", "finding.high_risk"]
    assert events[0]["data"] == events[1]["data"]


def test_just_below_threshold_is_not_high_risk(r, sub):
    set_thresholds(r, M2=0.5)
    RedisPublisher(r, clock=clock).publish_findings([created(score=0.49)])
    assert [e["type"] for e in sub()] == ["finding.created"]


def test_threshold_is_per_module(r, sub):
    set_thresholds(r, M1=0.9, M2=0.2)
    RedisPublisher(r, clock=clock).publish_findings([created(module="M1", score=0.5)])
    assert [e["type"] for e in sub()] == ["finding.created"]


def test_update_publishes_nothing(r, sub):
    RedisPublisher(r, clock=clock).publish_findings([SavedFinding(finding(score=0.99), "updated")])
    assert sub() == []


def test_update_does_not_read_thresholds(r, sub):
    r.set(THRESHOLDS_KEY, "not json")
    RedisPublisher(r, clock=clock).publish_findings([SavedFinding(finding(score=0.99), "updated")])
    assert r.threshold_gets == 0


# ---- live thresholds ----------------------------------------------------------------------------


def test_slider_moved_between_findings(r, sub):
    publisher = RedisPublisher(r, clock=clock)
    set_thresholds(r, M2=0.5)
    publisher.publish_findings([created(score=0.6)])
    set_thresholds(r, M2=0.7)
    publisher.publish_findings([created(score=0.6, fid="55555555-5555-4555-8555-555555555555")])
    assert [e["type"] for e in sub()] == ["finding.created", "finding.high_risk", "finding.created"]


def test_read_per_finding_without_cache(r):
    RedisPublisher(r, clock=clock).publish_findings(
        [created(), created(module="M1", fid="55555555-5555-4555-8555-555555555555")]
    )
    assert r.threshold_gets == 2


def test_slider_moved_inside_one_batch(r, sub):
    set_thresholds(r, M2=0.5)

    def moving_clock() -> datetime:  # called once per created finding, right after its threshold read
        set_thresholds(r, M2=0.7)
        return EMITTED

    RedisPublisher(r, clock=moving_clock).publish_findings(
        [created(score=0.6), created(score=0.6, fid="55555555-5555-4555-8555-555555555555")]
    )
    assert [e["type"] for e in sub()] == ["finding.created", "finding.high_risk", "finding.created"]


def test_key_missing_uses_default(r, sub, caplog):
    with caplog.at_level(logging.WARNING):
        RedisPublisher(r, clock=clock).publish_findings([created(module="M3", score=0.7)])
    assert [e["type"] for e in sub()] == ["finding.created", "finding.high_risk"]
    assert [rec.reason for rec in caplog.records] == ["thresholds_missing"]


@pytest.mark.parametrize(
    "raw",
    ['{"M2": "high"}', "not json", "[0.5]", '{"M2": 1.5}', '{"M2": -0.1}', '{"M2": true}', '{"M2": null}'],
)
def test_malformed_value_uses_default(r, caplog, raw):
    r.set(THRESHOLDS_KEY, raw)
    with caplog.at_level(logging.WARNING):
        thresholds = read_thresholds(r)
    assert thresholds["M2"] == DEFAULT_THRESHOLDS["M2"]
    assert [rec.reason for rec in caplog.records] == ["thresholds_invalid"]


def test_valid_key_logs_nothing(r, caplog):
    r.set(THRESHOLDS_KEY, '{"M1":0.1,"M2":0.2,"M3":0.3}')
    with caplog.at_level(logging.WARNING):
        assert read_thresholds(r) == {"M1": 0.1, "M2": 0.2, "M3": 0.3}
    assert caplog.records == []


def test_partial_key_keeps_valid_values(r, caplog):
    r.set(THRESHOLDS_KEY, '{"M2": 0.9}')
    with caplog.at_level(logging.WARNING):
        assert read_thresholds(r) == {"M1": 0.6, "M2": 0.9, "M3": 0.7}
    assert [rec.reason for rec in caplog.records] == ["thresholds_invalid"]


def test_integer_thresholds_are_accepted(r):
    r.set(THRESHOLDS_KEY, '{"M1": 1, "M2": 0, "M3": 0.7}')
    assert read_thresholds(r) == {"M1": 1.0, "M2": 0.0, "M3": 0.7}


def test_names_match_the_contract():
    # integration-plan §6 and ADR 0305; literal on purpose so a renamed constant is caught
    assert (EVENTS_CHANNEL, THRESHOLDS_KEY) == ("iw:events", "iw:settings:thresholds")


def test_defaults_match_adr_0305():
    assert DEFAULT_THRESHOLDS == {"M1": 0.6, "M2": 0.5, "M3": 0.7}


# ---- failures -----------------------------------------------------------------------------------


class DownRedis:
    def get(self, key):
        raise redis.ConnectionError("down")

    def publish(self, channel, message):
        raise redis.ConnectionError("down")


class PublishDownRedis(fakeredis.FakeRedis):
    def publish(self, channel, message):
        raise redis.ConnectionError("down")


@pytest.mark.parametrize("client", [DownRedis(), PublishDownRedis(decode_responses=True)], ids=["all-down", "publish-down"])
def test_publish_failure_is_logged_not_raised(client, caplog):
    with caplog.at_level(logging.WARNING):
        sent = RedisPublisher(client, clock=clock).publish_findings([created(score=0.9)])
    assert sent == []
    [rec] = [rec for rec in caplog.records if getattr(rec, "reason", None) == "publish_failed"]
    assert rec.finding_ids == ["44444444-4444-4444-8444-444444444444"]


class SecondPublishFails(fakeredis.FakeRedis):
    calls = 0

    def publish(self, channel, message):
        self.calls += 1
        if self.calls == 2:
            raise redis.ConnectionError("down")
        return super().publish(channel, message)


@pytest.mark.parametrize(
    "first_score,unsent",
    [(0.1, ["55555555-5555-4555-8555-555555555555"]),  # first finding fully sent, the second not at all
     (0.9, ["44444444-4444-4444-8444-444444444444", "55555555-5555-4555-8555-555555555555"])],  # high_risk lost
    ids=["second-finding-lost", "high-risk-lost"],
)
def test_partial_publish_reports_what_was_sent(caplog, first_score, unsent):
    client = SecondPublishFails(decode_responses=True)
    first, other = "44444444-4444-4444-8444-444444444444", "55555555-5555-4555-8555-555555555555"
    with caplog.at_level(logging.WARNING):
        sent = RedisPublisher(client, clock=clock).publish_findings(
            [created(score=first_score), created(score=0.1, fid=other)]
        )
    assert [(e["type"], e["data"]["id"]) for e in sent] == [("finding.created", first)]
    [rec] = [rec for rec in caplog.records if getattr(rec, "reason", None) == "publish_failed"]
    assert rec.finding_ids == unsent
    assert rec.sent == 1


def test_returns_the_events_sent(r):
    sent = RedisPublisher(r, clock=clock).publish_findings([created(score=0.9)])
    assert [e["type"] for e in sent] == ["finding.created", "finding.high_risk"]


# ---- no-op --------------------------------------------------------------------------------------


def test_noop_records_what_redis_would_send(r, sub):
    set_thresholds(r, M2=0.4)
    batch = [created(score=0.45), created(module="M1", score=0.1, fid="55555555-5555-4555-8555-555555555555"),
             SavedFinding(finding(score=0.9, fid="66666666-6666-4666-8666-666666666666"), "updated")]
    RedisPublisher(r, clock=clock).publish_findings(batch)
    noop = NoopPublisher(thresholds={**DEFAULT_THRESHOLDS, "M2": 0.4}, clock=clock)
    noop.publish_findings(batch)
    assert noop.sent == sub()
    assert len(noop.sent) == 3


def test_noop_defaults_to_adr_thresholds():
    noop = NoopPublisher(clock=clock)
    noop.publish_findings([created(module="M3", score=0.7)])
    assert [e["type"] for e in noop.sent] == ["finding.created", "finding.high_risk"]
