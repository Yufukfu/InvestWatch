"""Persistence behind one interface: load a `ScrapedDocument`, store its `Finding`s.

Tables come from the API's Alembic migrations (ADR 0303, change `api-db-schema`); this module only reads and
writes rows. A finding is identified by `(document_id, module)`: saving the same document again updates its
finding in place and never touches `id`, `detected_at`, `status` or `note` (analysts own the last two).
Spec: openspec/changes/analytics-worker/specs/finding-storage/spec.md.
"""

from __future__ import annotations

import copy
import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from pydantic import ValidationError

from .models import Finding, ScrapedDocument

#: Fields replaced on an update. Everything else on an existing row is kept.
#: Mirrors `UPSERT_REPLACED` in api-db-schema (`api/src/investwatch_api/db/sql.py`); `advertiser` joins once
#: the `Finding` model carries it.
ANALYSIS_FIELDS = (
    "score", "title", "summary", "firm", "rules", "content_excerpt", "url", "platform", "model", "updated_at",
)


class StoreError(Exception):
    """Base class of every store outcome other than success."""


class NotFound(StoreError):
    """No `documents` row with that id (the worker acks with `document_not_found`)."""


class InvalidDocument(StoreError):
    """The row does not satisfy `ScrapedDocument` (the worker acks with `invalid_document`)."""

    def __init__(self, field: str, message: str) -> None:
        super().__init__(f"{field}: {message}")
        self.field = field


class StoreUnavailable(StoreError):
    """Connection loss or a serialization failure: retry later, never ack."""


@dataclass(frozen=True)
class SavedFinding:
    finding: Finding
    outcome: Literal["created", "updated"]


class Store(Protocol):
    def load_document(self, document_id: str) -> ScrapedDocument: ...

    def save_findings(self, document: ScrapedDocument, findings: Sequence[Finding]) -> list[SavedFinding]: ...

    def findings_for_document(self, document_id: str) -> list[Finding]: ...


def document_from_row(columns: Mapping[str, Any], payload: Mapping[str, Any] | None) -> ScrapedDocument:
    """Merge `payload` JSONB with the scalar columns (columns win) and validate."""
    merged = {**(payload or {}), **columns}
    try:
        return ScrapedDocument.model_validate(merged)
    except ValidationError as exc:
        first = exc.errors()[0]
        field = ".".join(str(part) for part in first["loc"]) or "<document>"
        raise InvalidDocument(field, first["msg"]) from exc


class InMemoryStore:
    """Test store with the same observable behaviour as the Postgres store."""

    def __init__(self) -> None:
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
        return document_from_row(*row)

    def save_findings(self, document: ScrapedDocument, findings: Sequence[Finding]) -> list[SavedFinding]:
        with self._lock:
            self._check()
            staged = copy.copy(self._findings)  # one "transaction": swap in only when every write succeeded
            saved: list[SavedFinding] = []
            for f in findings:
                if f.document_id not in self._documents:
                    raise StoreError(f"foreign key: document {f.document_id} does not exist")
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
