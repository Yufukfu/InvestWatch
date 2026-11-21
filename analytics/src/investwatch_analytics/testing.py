"""Test doubles for the worker, outside the service: `worker.main` never imports this module.

`InMemoryStore` behaves like `PostgresStore` for every finding-storage scenario; `NoopPublisher` makes the same
event decisions as `RedisPublisher` with fixed thresholds and records instead of sending.
"""

from __future__ import annotations

import copy
import json as _json
import threading
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from typing import Any

from .events import DEFAULT_THRESHOLDS, Clock, Publisher, _utc_now
from .models import Finding, ScrapedDocument
from .storage import (
    ANALYSIS_FIELDS,
    DEFAULT_MAX_DOCUMENT_BYTES,
    NotFound,
    SavedFinding,
    StoreError,
    StoreUnavailable,
    _too_large,
    document_from_row,
)

__all__ = ["InMemoryStore", "NoopPublisher"]


class InMemoryStore:
    """Test store with the same observable behaviour as the Postgres store."""

    def __init__(self, *, max_document_bytes: int = DEFAULT_MAX_DOCUMENT_BYTES) -> None:
        self._max_document_bytes = max_document_bytes
        self._lock = threading.Lock()
        self._documents: dict[str, tuple[dict, dict | None]] = {}
        self._findings: dict[tuple[str, str], Finding] = {}
        #: Set to True to simulate an outage: every operation raises `StoreUnavailable`.
        self.unavailable = False
        #: Test seam called between staging and commit, so a test can interleave two saves.
        self.before_commit: Callable[[], None] | None = None

    # -- test helpers (the scraper and the API write these in production) --------------------------

    def put_document_row(self, columns: Mapping[str, Any], payload: Mapping[str, Any] | None = None) -> None:
        self._documents[str(columns["id"])] = (dict(columns), dict(payload) if payload is not None else None)

    def set_review(self, document_id: str, module: str, *, status: str, note: str | None) -> None:
        key = (document_id, module)
        self._findings[key] = self._findings[key].model_copy(update={"status": status, "note": note})

    # -- Store -------------------------------------------------------------------------------------

    def _check(self) -> None:
        if self.unavailable:
            raise StoreUnavailable("in-memory store marked unavailable")

    def load_document(self, document_id: str) -> ScrapedDocument:
        self._check()
        row = self._documents.get(document_id)
        if row is None:
            raise NotFound(document_id)
        columns, payload = row
        size = len(str(columns.get("text") or "").encode("utf-8")) + len(_json.dumps(payload or {}).encode("utf-8"))
        if size > self._max_document_bytes:
            raise _too_large(size, self._max_document_bytes)
        return document_from_row(columns, payload)

    def save_findings(self, document: ScrapedDocument, findings: Sequence[Finding]) -> list[SavedFinding]:
        with self._lock:
            self._check()
            staged = copy.copy(self._findings)  # one "transaction": swap in only when every write succeeded
            saved: list[SavedFinding] = []
            for f in findings:
                if f.document_id not in self._documents:
                    raise StoreError("ForeignKeyViolation (sqlstate 23503)")  # same text as the Postgres store
                key = (f.document_id, f.module)
                existing = staged.get(key)
                if existing is None:
                    row = f.model_copy(update={"status": "new", "note": None})
                    outcome = "created"
                else:
                    row = existing.model_copy(update={name: getattr(f, name) for name in ANALYSIS_FIELDS})
                    outcome = "updated"
                staged[key] = row
                saved.append(SavedFinding(row, outcome))
            if self.before_commit is not None:
                self.before_commit()
            self._findings = staged
            return saved

    def findings_for_document(self, document_id: str) -> list[Finding]:
        self._check()
        return [f for (doc_id, _), f in sorted(self._findings.items()) if doc_id == document_id]


class NoopPublisher(Publisher):
    """Same decisions as `RedisPublisher` with fixed thresholds; records events instead of sending them."""

    def __init__(self, thresholds: Mapping[str, float] | None = None, clock: Clock = _utc_now) -> None:
        super().__init__(clock)
        self._fixed = dict(DEFAULT_THRESHOLDS if thresholds is None else thresholds)
        self.sent: list[dict[str, Any]] = []

    def _thresholds(self) -> Mapping[str, float]:
        return self._fixed

    def _send_one(self, event: dict[str, Any]) -> None:
        self.sent.append(event)
