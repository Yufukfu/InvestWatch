"""Persistence behind one interface: load a `ScrapedDocument`, store its `Finding`s.

Tables come from the API's Alembic migrations (ADR 0303, change `api-db-schema`); this module only reads and
writes rows. A finding is identified by `(document_id, module)`: saving the same document again updates its
finding in place and never touches `id`, `detected_at`, `status` or `note` (analysts own the last two).
Spec: openspec/changes/analytics-worker/specs/finding-storage/spec.md.
"""

from __future__ import annotations

import copy
import threading
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from pydantic import ValidationError

from .models import Finding, ScrapedDocument

#: Fields replaced on an update. Everything else on an existing row is kept.
#: Mirrors `UPSERT_REPLACED` in api-db-schema (`api/src/investwatch_api/db/sql.py`).
ANALYSIS_FIELDS = (
    "score", "title", "summary", "firm", "advertiser", "rules", "content_excerpt", "url", "platform", "model",
    "updated_at",
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


class StoreMisconfigured(StoreError):
    """`DATABASE_URL` cannot be parsed. Not retryable: the worker exits. The message never quotes the URL."""


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


# ---- Postgres -----------------------------------------------------------------------------------

#: Scalar `documents` columns (api-db-schema revision 0001); everything else lives in `payload`.
DOCUMENT_COLUMNS = (
    "id", "source_id", "platform", "source_kind", "url", "canonical_url", "fetched_at", "published_at",
    "http_status", "lang", "title", "text", "content_hash", "html_object_key",
)
#: `findings` columns analytics reads back into a `Finding`.
FINDING_COLUMNS = (
    "id", "document_id", "module", "score", "status", "title", "summary", "firm", "advertiser", "rules",
    "content_excerpt", "url", "platform", "note", "detected_at", "updated_at", "model",
)
_JSON_COLUMNS = ("firm", "advertiser", "rules", "model")
_INSERT_COLUMNS = (
    "id", "document_id", "module", "score", "status", "title", "summary", "firm", "advertiser", "rules",
    "content_excerpt", "url", "platform", "detected_at", "updated_at", "model",
)
#: The upsert documented in api/README.md (`findings_upsert()` in api-db-schema). Keeps id, detected_at,
#: status and note; `xmax = 0` is true only for a freshly inserted row.
_UPSERT_SQL = (
    f"INSERT INTO findings ({', '.join(_INSERT_COLUMNS)}) "
    f"VALUES ({', '.join(['%s'] * len(_INSERT_COLUMNS))}) "
    "ON CONFLICT ON CONSTRAINT uq_findings_document_module DO UPDATE SET "
    + ", ".join(
        f"{c} = excluded.{c}"
        for c in ANALYSIS_FIELDS
    )
    + f" RETURNING {', '.join(FINDING_COLUMNS)}, (xmax = 0) AS inserted"
)
_LOAD_SQL = f"SELECT {', '.join(DOCUMENT_COLUMNS)}, payload FROM documents WHERE id = %s"
_FINDINGS_SQL = f"SELECT {', '.join(FINDING_COLUMNS)} FROM findings WHERE document_id = %s ORDER BY module"


def _plain(value: Any) -> Any:
    return str(value) if isinstance(value, uuid.UUID) else value


def _finding_from_row(row: Mapping[str, Any]) -> Finding:
    return Finding.model_validate({c: _plain(row[c]) for c in FINDING_COLUMNS})


class PostgresStore:
    """Store on the shared Postgres (connect as `iw_app`). One connection per thread, reopened after a drop."""

    def __init__(self, dsn: str, *, connect_timeout: int = 5) -> None:
        from psycopg.conninfo import conninfo_to_dict

        try:
            conninfo_to_dict(dsn)
            malformed = False
        except Exception:
            malformed = True
        if malformed:  # raised outside the except block, so the libpq error (it may quote the password) is not kept
            raise StoreMisconfigured("DATABASE_URL is malformed")
        self._dsn = dsn
        self._connect_timeout = connect_timeout
        self._local = threading.local()
        self._all: list[Any] = []
        self._all_lock = threading.Lock()

    def _conn(self):
        import psycopg
        from psycopg.rows import dict_row

        conn = getattr(self._local, "conn", None)
        if conn is None or conn.closed:
            conn = psycopg.connect(self._dsn, autocommit=True, row_factory=dict_row,
                                   connect_timeout=self._connect_timeout)
            self._local.conn = conn
            with self._all_lock:
                self._all.append(conn)
        return conn

    def _drop_conn(self) -> None:
        conn = getattr(self._local, "conn", None)
        self._local.conn = None
        if conn is not None:
            with self._all_lock:
                if conn in self._all:
                    self._all.remove(conn)
            try:
                conn.close()
            except Exception:  # already broken; nothing left to release
                pass

    def _run(self, op: Callable[[Any], Any]) -> Any:
        """Run `op(conn)` and translate driver errors into the store's taxonomy."""
        import psycopg
        from psycopg import errors

        try:
            return op(self._conn())
        except (errors.SerializationFailure, errors.DeadlockDetected) as exc:
            raise StoreUnavailable(f"retryable conflict: {type(exc).__name__}") from exc
        except (psycopg.OperationalError, psycopg.InterfaceError) as exc:
            self._drop_conn()
            # libpq messages name host and port, never the password; still keep only the class and the
            # first line so a DSN can never reach the logs.
            first_line = str(exc).strip().splitlines()[0] if str(exc).strip() else ""
            raise StoreUnavailable(f"{type(exc).__name__}: {first_line}") from exc
        except psycopg.Error as exc:
            # e.g. an FK violation (IntegrityError), InsufficientPrivilege (a missing grant) or DataError:
            # unexpected, so the worker counts it toward MAX_DELIVERIES. Only the class and SQLSTATE, never the
            # message: driver messages can echo row values ("Key (document_id)=(...)").
            raise StoreError(f"{type(exc).__name__} (sqlstate {exc.sqlstate})") from None

    def load_document(self, document_id: str) -> ScrapedDocument:
        try:
            key = uuid.UUID(document_id)
        except (ValueError, AttributeError, TypeError):
            raise NotFound(str(document_id)) from None
        row = self._run(lambda conn: conn.execute(_LOAD_SQL, (key,)).fetchone())
        if row is None:
            raise NotFound(document_id)
        payload = row.pop("payload") or {}
        return document_from_row({c: _plain(v) for c, v in row.items()}, payload)

    def save_findings(self, document: ScrapedDocument, findings: Sequence[Finding]) -> list[SavedFinding]:
        from psycopg.types.json import Jsonb

        def params(f: Finding) -> list[Any]:
            data = f.model_dump(mode="json")
            values = {
                **{c: getattr(f, c, None) for c in _INSERT_COLUMNS},
                "id": uuid.UUID(f.id),
                "document_id": uuid.UUID(f.document_id),
                "status": "new",
                "detected_at": f.detected_at,
                "updated_at": f.updated_at,
            }
            for c in _JSON_COLUMNS:
                values[c] = Jsonb(data[c]) if data.get(c) is not None else None
            values["rules"] = Jsonb(data["rules"])
            return [values[c] for c in _INSERT_COLUMNS]

        def op(conn) -> list[SavedFinding]:
            saved = []
            with conn.transaction():
                for f in findings:
                    row = conn.execute(_UPSERT_SQL, params(f)).fetchone()
                    saved.append(SavedFinding(_finding_from_row(row), "created" if row["inserted"] else "updated"))
            return saved

        return self._run(op)

    def findings_for_document(self, document_id: str) -> list[Finding]:
        try:
            key = uuid.UUID(document_id)
        except (ValueError, AttributeError, TypeError):
            return []  # same as the in-memory store: no finding can belong to a non-UUID id
        rows = self._run(lambda conn: conn.execute(_FINDINGS_SQL, (key,)).fetchall())
        return [_finding_from_row(r) for r in rows]

    def ping(self) -> bool:
        """`SELECT 1` for /health on a short-lived connection, closed before returning; False instead of raising.

        Never the per-thread connection: the health server runs each request on a new thread, and a cached
        connection per request would leak one Postgres slot per health check.
        """
        import psycopg

        try:
            with psycopg.connect(self._dsn, connect_timeout=self._connect_timeout) as conn:
                conn.execute("SELECT 1").fetchone()
            return True
        except Exception:  # down, auth, anything: the check only answers yes or no
            return False

    def close(self) -> None:
        with self._all_lock:
            conns, self._all = self._all, []
        for conn in conns:
            try:
                conn.close()
            except Exception:  # best effort at shutdown
                pass
