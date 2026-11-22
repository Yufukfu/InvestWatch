"""Events on Redis Pub/Sub `iw:events` (`.docs/integration-plan.md` §6, `contracts/schemas/events.schema.json`).

Per finding the store reports `created`: one `finding.created`, then `finding.high_risk` when `score` is at or
above the module threshold. The threshold is read from Redis `iw:settings:thresholds` for each such finding,
never cached (ADR 0305). A finding reported `updated` publishes nothing. Analytics never computes `risk_level`.
Events are at most once: a publish failure is logged with the finding ids and never raised, because the
findings are already committed. A near-duplicate group (analytics-embeddings, `neardup.py`) gets at most one
`finding.high_risk` per module: the first alert claims `iw:neardup:v1:alerted:{group}:{module}` with
`SET NX`; later members still publish `finding.created`. A failed claim fails open (the alert is sent).
Spec: openspec/specs/finding-events/spec.md.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

import redis

from .models import Finding
from .storage import SavedFinding

log = logging.getLogger(__name__)

EVENTS_CHANNEL = "iw:events"
THRESHOLDS_KEY = "iw:settings:thresholds"
#: Defaults per module when the key or its value is missing or invalid. A copy of analytics/eval/thresholds.json,
#: the best-F1 thresholds of the gold-set evaluation (ADR 0316, superseding ADR 0305's values); a test pins it.
DEFAULT_THRESHOLDS: dict[str, float] = {"M1": 0.75, "M2": 0.1, "M3": 0.4}

Clock = Callable[[], datetime]
#: Same lifetime as the near-dup group keys (NEARDUP_TTL_S default).
ALERT_TTL_S = 2_592_000


def alert_key(group_id: str, module: str) -> str:
    return f"iw:neardup:v1:alerted:{group_id}:{module}"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _valid_threshold(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 1


def parse_thresholds(raw: str | bytes | None) -> tuple[dict[str, float], str | None]:
    """Thresholds per module from the key's raw value, and the reason any default was used (or None)."""
    if raw is None:
        return dict(DEFAULT_THRESHOLDS), "thresholds_missing"
    try:
        data = json.loads(raw)
    except ValueError:
        return dict(DEFAULT_THRESHOLDS), "thresholds_invalid"
    if not isinstance(data, dict):
        return dict(DEFAULT_THRESHOLDS), "thresholds_invalid"
    result, reason = {}, None
    for module, default in DEFAULT_THRESHOLDS.items():
        value = data.get(module)
        if _valid_threshold(value):
            result[module] = float(value)
        else:
            result[module], reason = default, "thresholds_invalid"
    return result, reason


def read_thresholds(client: Any) -> dict[str, float]:
    """GET the key (no cache) and fall back per module to the defaults, logging the reason once."""
    thresholds, reason = parse_thresholds(client.get(THRESHOLDS_KEY))
    if reason is not None:
        log.warning("thresholds fallback to defaults", extra={"reason": reason, "thresholds": thresholds})
    return thresholds


def finding_brief(finding: Finding) -> dict[str, Any]:
    """`finding_brief` from the events schema; deliberately without `risk_level`."""
    return {
        "id": finding.id,
        "module": finding.module,
        "score": finding.score,
        "title": finding.title,
        "url": finding.url,
        "platform": finding.platform,
    }


def make_event(event_type: str, finding: Finding, emitted_at: datetime) -> dict[str, Any]:
    stamp = emitted_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return {"type": event_type, "emitted_at": stamp, "data": finding_brief(finding)}


class Publisher:
    """Decides which events a save result produces; subclasses read thresholds and send."""

    def __init__(self, clock: Clock = _utc_now, alert_ttl_s: int = ALERT_TTL_S) -> None:
        self._clock = clock
        self._alert_ttl_s = alert_ttl_s

    def _thresholds(self) -> Mapping[str, float]:
        raise NotImplementedError

    def _claim(self, group_id: str, module: str) -> bool:
        """True if this is the group's first alert for the module (atomic); may raise a Redis error."""
        raise NotImplementedError

    def _may_alert(self, finding: Finding, groups: Mapping[str, str] | None) -> bool:
        group_id = groups.get(finding.document_id) if groups else None
        if not group_id:
            return True
        try:
            first = self._claim(group_id, finding.module)
        except redis.RedisError as exc:
            log.warning("near-dup alert claim failed; alert sent", extra={
                "reason": "neardup_claim_failed", "finding_id": finding.id, "error": type(exc).__name__})
            return True
        if not first:
            log.info("high_risk_suppressed", extra={"reason": "neardup", "finding_id": finding.id,
                                                    "group_id": group_id, "finding_module": finding.module})
        return first

    def _send_one(self, event: dict[str, Any]) -> None:
        raise NotImplementedError

    def _events_for(self, saved: Sequence[SavedFinding]) -> list[tuple[dict[str, Any], Finding | None]]:
        """Planned events in order; a `finding.high_risk` carries its finding, so the send loop can claim the
        near-dup alert right before sending it (a failed PUBLISH then burns at most that one claim)."""
        events: list[tuple[dict[str, Any], Finding | None]] = []
        for item in saved:
            if item.outcome != "created":
                continue
            threshold = self._thresholds()[item.finding.module]
            emitted_at = self._clock()
            events.append((make_event("finding.created", item.finding, emitted_at), None))
            if item.finding.score >= threshold:
                events.append((make_event("finding.high_risk", item.finding, emitted_at), item.finding))
        return events

    def publish_findings(self, saved: Sequence[SavedFinding],
                         groups: Mapping[str, str] | None = None) -> list[dict[str, Any]]:
        """Publish the events for one committed save; returns the events actually sent.

        `groups` maps a document id to its near-dup group id (`NearDupResult.group_id`); without it every
        high-risk finding alerts, as before.

        On a Redis error the rest is dropped (events are at most once) and the log names the findings whose
        events were not all sent.
        """
        sent: list[dict[str, Any]] = []
        events: list[tuple[dict[str, Any], Finding | None]] | None = None
        position = 0
        try:
            events = self._events_for(saved)
            for position, (event, gated) in enumerate(events):
                if gated is not None and not self._may_alert(gated, groups):
                    continue
                self._send_one(event)
                sent.append(event)
        except redis.RedisError as exc:
            if events is None:  # thresholds could not be read, so nothing was sent
                unsent = [s.finding.id for s in saved if s.outcome == "created"]
            else:
                unsent = list(dict.fromkeys(e["data"]["id"] for e, _ in events[position:]))
            log.warning(
                "event publish failed; findings stay committed",
                extra={"reason": "publish_failed", "finding_ids": unsent, "sent": len(sent), "error": str(exc)},
            )
        return sent


class RedisPublisher(Publisher):
    def __init__(self, client: Any, clock: Clock = _utc_now, alert_ttl_s: int = ALERT_TTL_S) -> None:
        super().__init__(clock, alert_ttl_s)
        self._client = client

    def _thresholds(self) -> Mapping[str, float]:
        return read_thresholds(self._client)

    def _claim(self, group_id: str, module: str) -> bool:
        return bool(self._client.set(alert_key(group_id, module), "1", nx=True, ex=self._alert_ttl_s))

    def _send_one(self, event: dict[str, Any]) -> None:
        self._client.publish(EVENTS_CHANNEL, json.dumps(event, ensure_ascii=False))
