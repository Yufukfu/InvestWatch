"""No repeat high-risk alert for a near-duplicate group (analytics-embeddings task group 8a; finding-events delta)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import fakeredis
import pytest
import redis

from conftest import NOW
from investwatch_analytics.events import EVENTS_CHANNEL, RedisPublisher, alert_key
from investwatch_analytics.models import Finding
from investwatch_analytics.storage import SavedFinding
from investwatch_analytics.testing import NoopPublisher

EMITTED = datetime(2026, 11, 21, 16, 30, tzinfo=timezone.utc)
ORIG_DOC = "22222222-2222-4222-8222-222222222222"
COPY_DOC = "33333333-3333-4333-8333-333333333333"
THIRD_DOC = "55555555-5555-4555-8555-555555555555"


def clock():
    return EMITTED


def created(doc=ORIG_DOC, module="M1", score=0.9, fid=None, url="https://x.com/a/1") -> SavedFinding:
    return SavedFinding(Finding(
        id=fid or doc.replace(doc[:8], "44444444"), document_id=doc, module=module, score=score,
        title="Sygnały inwestycyjne", rules=[], url=url, platform="x", detected_at=NOW, updated_at=NOW,
    ), "created")


def types(events):
    return [(e["type"], e["data"]["id"]) for e in events]


@pytest.fixture
def r():
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def pub(r):
    return RedisPublisher(r, clock=clock)


GROUP = {ORIG_DOC: ORIG_DOC, COPY_DOC: ORIG_DOC, THIRD_DOC: ORIG_DOC}


# ---- unchanged behaviour ----------------------------------------------------------------------


def test_no_groups_behaves_as_before(pub):
    a, b = created(), created(doc=COPY_DOC)
    sent = pub.publish_findings([a]) + pub.publish_findings([b])
    assert [t for t, _ in types(sent)] == ["finding.created", "finding.high_risk"] * 2


def test_document_without_group_behaves_as_before(pub):
    sent = pub.publish_findings([created()], groups={COPY_DOC: ORIG_DOC})
    assert [t for t, _ in types(sent)] == ["finding.created", "finding.high_risk"]


def test_updated_still_publishes_nothing(pub):
    assert pub.publish_findings([SavedFinding(created().finding, "updated")], groups=GROUP) == []


# ---- suppression ------------------------------------------------------------------------------


def test_near_duplicate_of_an_alerted_document(pub, caplog):
    first = pub.publish_findings([created()], groups=GROUP)
    copy = created(doc=COPY_DOC, url="https://x.com/b/9")
    with caplog.at_level(logging.INFO):
        second = pub.publish_findings([copy], groups=GROUP)
    assert [t for t, _ in types(first)] == ["finding.created", "finding.high_risk"]
    assert types(second) == [("finding.created", copy.finding.id)]
    assert second[0]["data"]["url"] == "https://x.com/b/9"
    rec = [x for x in caplog.records if x.getMessage() == "high_risk_suppressed"]
    assert rec and rec[0].reason == "neardup" and rec[0].finding_id == copy.finding.id
    assert rec[0].group_id == ORIG_DOC


def test_low_score_original_does_not_block_its_copy(pub):
    assert [t for t, _ in types(pub.publish_findings([created(score=0.1)], groups=GROUP))] == ["finding.created"]
    copy = pub.publish_findings([created(doc=COPY_DOC)], groups=GROUP)
    third = pub.publish_findings([created(doc=THIRD_DOC)], groups=GROUP)
    assert [t for t, _ in types(copy)] == ["finding.created", "finding.high_risk"]
    assert [t for t, _ in types(third)] == ["finding.created"]


def test_other_module_not_suppressed(pub):
    pub.publish_findings([created(module="M1")], groups=GROUP)
    m3 = pub.publish_findings([created(doc=COPY_DOC, module="M3", score=0.8)], groups=GROUP)
    assert [t for t, _ in types(m3)] == ["finding.created", "finding.high_risk"]


def test_two_findings_of_one_group_in_one_save(pub):
    sent = pub.publish_findings([created(), created(doc=COPY_DOC)], groups=GROUP)
    assert [t for t, _ in types(sent)] == ["finding.created", "finding.high_risk", "finding.created"]


def test_claim_key_has_ttl(r):
    RedisPublisher(r, clock=clock, alert_ttl_s=120).publish_findings([created()], groups=GROUP)
    assert alert_key(ORIG_DOC, "M1") == f"iw:neardup:v1:alerted:{ORIG_DOC}:M1"
    assert 0 < r.ttl(alert_key(ORIG_DOC, "M1")) <= 120


class ClaimFails(fakeredis.FakeRedis):
    def set(self, name, *a, **k):
        if str(name).startswith("iw:neardup:v1:alerted:"):
            raise redis.ConnectionError("down")
        return super().set(name, *a, **k)


def test_claim_fails_open(caplog):
    r = ClaimFails(decode_responses=True)
    pub = RedisPublisher(r, clock=clock)
    with caplog.at_level(logging.WARNING):
        a = pub.publish_findings([created()], groups=GROUP)
        b = pub.publish_findings([created(doc=COPY_DOC)], groups=GROUP)
    assert [t for t, _ in types(a + b)] == ["finding.created", "finding.high_risk"] * 2
    assert any(getattr(x, "reason", None) == "neardup_claim_failed" for x in caplog.records)
    assert not any(getattr(x, "reason", None) == "publish_failed" for x in caplog.records)


def test_events_reach_the_channel(r):
    ps = r.pubsub()
    ps.subscribe(EVENTS_CHANNEL)
    ps.get_message(timeout=1)
    pub = RedisPublisher(r, clock=clock)
    pub.publish_findings([created()], groups=GROUP)
    pub.publish_findings([created(doc=COPY_DOC)], groups=GROUP)
    got = []
    while (m := ps.get_message(timeout=0.05)) is not None:
        got.append(json.loads(m["data"])["type"])
    assert got == ["finding.created", "finding.high_risk", "finding.created"]


# ---- no-op publisher matches ------------------------------------------------------------------


def test_noop_publisher_makes_the_same_decisions(r):
    redis_pub, noop = RedisPublisher(r, clock=clock), NoopPublisher(clock=clock)
    for item in [created(), created(doc=COPY_DOC), created(doc=THIRD_DOC, module="M3")]:
        assert redis_pub.publish_findings([item], groups=GROUP) == noop.publish_findings([item], groups=GROUP)
