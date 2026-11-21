"""finding-storage scenarios (openspec/changes/analytics-worker/specs/finding-storage/spec.md).

The suite runs on every store backend in STORE_BACKENDS. The Postgres backend needs TEST_DATABASE_URL (a
throwaway server; the URL's role must be allowed to CREATE DATABASE) and is skipped without it. Each test
session creates its own database from tests/sql/schema.sql (a test-only mirror of the api-db-schema
migration) and drops it at the end.
"""

from __future__ import annotations

import os
import pathlib
import threading
import time
import uuid
from datetime import timedelta

import pytest

from conftest import NOW, make_doc
from investwatch_analytics.models import Finding, ScrapedDocument
from investwatch_analytics.storage import (
    InMemoryStore,
    InvalidDocument,
    NotFound,
    PostgresStore,
    StoreError,
    StoreUnavailable,
)

DOC_ID = "22222222-2222-4222-8222-222222222222"
DOC2_ID = "33333333-3333-4333-8333-333333333333"
MISSING_ID = "99999999-9999-4999-8999-999999999999"


class InMemoryBackend:
    def __init__(self) -> None:
        self.store = InMemoryStore()

    def seed(self, columns: dict, payload: dict | None = None) -> None:
        self.store.put_document_row(columns, payload)

    def set_status(self, document_id: str, module: str, status: str, note: str | None) -> None:
        self.store.set_review(document_id, module, status=status, note=note)

    def widen_race_window(self) -> None:
        # time.sleep releases the GIL, so without the store's lock both saves stage from the same snapshot.
        self.store.before_commit = lambda: time.sleep(0.05)


SCHEMA_SQL = pathlib.Path(__file__).parent / "sql" / "schema.sql"


@pytest.fixture(scope="session")
def pg_url():
    admin_url = os.environ.get("TEST_DATABASE_URL")
    if not admin_url:
        pytest.skip("TEST_DATABASE_URL not set")
    import psycopg
    from psycopg.conninfo import make_conninfo

    name = f"iw_test_analytics_{uuid.uuid4().hex[:10]}"
    with psycopg.connect(admin_url, autocommit=True) as conn:
        conn.execute(f'CREATE DATABASE "{name}"')
    url = make_conninfo(admin_url, dbname=name)
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(SCHEMA_SQL.read_text(encoding="utf-8"))
    yield url
    with psycopg.connect(admin_url, autocommit=True) as conn:
        conn.execute(f'DROP DATABASE "{name}" WITH (FORCE)')


class PostgresBackend:
    def __init__(self, url: str) -> None:
        import psycopg

        self._psycopg = psycopg
        self.url = url
        with psycopg.connect(url, autocommit=True) as conn:
            conn.execute("TRUNCATE findings, documents, sources CASCADE")
        self.store = PostgresStore(url)

    def seed(self, columns: dict, payload: dict | None = None) -> None:
        from psycopg import sql
        from psycopg.types.json import Jsonb

        row = {**columns, "payload": Jsonb(payload or {})}
        query = sql.SQL("INSERT INTO documents ({}) VALUES ({})").format(
            sql.SQL(", ").join(map(sql.Identifier, row)), sql.SQL(", ").join(sql.Placeholder() * len(row))
        )
        with self._psycopg.connect(self.url, autocommit=True) as conn:
            conn.execute(query, list(row.values()))

    def set_status(self, document_id: str, module: str, status: str, note: str | None) -> None:
        with self._psycopg.connect(self.url, autocommit=True) as conn:
            conn.execute(
                "UPDATE findings SET status = %s, note = %s WHERE document_id = %s AND module = %s",
                (status, note, document_id, module),
            )

    def widen_race_window(self) -> None:
        """Nothing to widen: two connections race for real and the unique constraint decides."""

    def close(self) -> None:
        self.store.close()


STORE_BACKENDS = [InMemoryBackend, PostgresBackend]


@pytest.fixture(params=STORE_BACKENDS, ids=lambda b: b.__name__)
def backend(request):
    if request.param is PostgresBackend:
        b = PostgresBackend(request.getfixturevalue("pg_url"))
        yield b
        b.close()
    else:
        yield request.param()


HASH_A, HASH_B = "a" * 64, "b" * 64


def columns(**overrides) -> dict:
    doc = make_doc(id=DOC_ID, title="Konto Premium", content_hash=HASH_A)
    doc.update(overrides)
    return doc


def finding(document_id: str = DOC_ID, module: str = "M2", score: float = 0.4, fid: str | None = None) -> Finding:
    return Finding(
        id=fid or "44444444-4444-4444-8444-444444444444",
        document_id=document_id,
        module=module,
        score=score,
        title="Brak oznaczenia reklamy",
        summary="Materiał nie jest oznaczony jako reklama.",
        rules=[{"rule_id": "R2", "name": "Oznaczenie reklamy", "result": "fail", "severity": "medium"}],
        content_excerpt="Przykładowy tekst.",
        firm={"name": "Alfa Inwestycje Dom Maklerski S.A.", "registry_id": "0b6d2f1e-3c4a-4b5d-8e6f-7a8b9c0d1e2f",
              "registry_type": "brokerage_house", "authorized": True, "match_confidence": 0.95},
        url="https://example.com/oferta",
        platform="web",
        detected_at=NOW,
        updated_at=NOW,
        model={"pipeline_version": "0.1.0", "llm": None},
    )


def load(backend, document_id: str = DOC_ID) -> ScrapedDocument:
    return backend.store.load_document(document_id)


# ---- load ---------------------------------------------------------------------------------------


def test_load_merges_payload_with_columns(backend):
    payload = {
        "links": [{"href": "https://example.com/r", "text": "Otwórz konto", "rel": "sponsored"}],
        "author": {"name": "Jan", "handle": "@jan"},
        "blocks": [{"viewport": "desktop", "text": "Zysk 20%", "font_size_px": 32, "visible": True}],
        "url": "https://payload-loses.example.com/",
    }
    backend.seed(columns(), payload)
    doc = load(backend)
    expected = ScrapedDocument.model_validate({**payload, **columns()})
    assert doc == expected
    assert doc.url == "https://example.com/oferta"  # the column wins over the payload
    assert doc.links[0].rel == "sponsored"


def test_load_without_payload(backend):
    backend.seed(columns(), None)
    assert load(backend).id == DOC_ID


def test_load_unknown_id_is_not_found(backend):
    with pytest.raises(NotFound):
        load(backend, MISSING_ID)


def test_load_invalid_column_names_the_field(backend):
    # The schema's NOT NULL and CHECKs stop most bad rows; a non-http URL still gets through.
    backend.seed(columns(url="ftp://example.com/oferta"))
    with pytest.raises(InvalidDocument) as err:
        load(backend)
    assert err.value.field == "url"


def test_load_invalid_payload_names_the_field(backend):
    backend.seed(columns(), {"blocks": [{"viewport": "watch", "text": "x", "font_size_px": 12, "visible": True}]})
    with pytest.raises(InvalidDocument) as err:
        load(backend)
    assert err.value.field == "blocks.0.viewport"


def test_load_malformed_id_is_not_found(backend):
    with pytest.raises(NotFound):
        load(backend, "not-a-uuid")


# ---- save ---------------------------------------------------------------------------------------


def test_first_analysis_inserts_with_status_new(backend):
    backend.seed(columns())
    doc = load(backend)
    [saved] = backend.store.save_findings(doc, [finding()])
    assert saved.outcome == "created"
    assert saved.finding.status == "new"
    assert saved.finding.id == "44444444-4444-4444-8444-444444444444"
    # full round trip: every field the pipeline produced comes back unchanged (JSON columns, timestamps)
    assert saved.finding.model_dump(exclude={"status", "note"}) == finding().model_dump(exclude={"status", "note"})
    assert backend.store.findings_for_document(DOC_ID) == [saved.finding]


def test_insert_never_takes_status_or_note_from_the_pipeline(backend):
    backend.seed(columns())
    f = finding().model_copy(update={"status": "confirmed", "note": "x"})
    [saved] = backend.store.save_findings(load(backend), [f])
    assert (saved.finding.status, saved.finding.note) == ("new", None)


def test_same_document_again_updates_in_place(backend):
    backend.seed(columns())
    doc = load(backend)
    [first] = backend.store.save_findings(doc, [finding(score=0.4)])
    later = NOW + timedelta(minutes=5)
    again = finding(score=0.9, fid="55555555-5555-4555-8555-555555555555").model_copy(
        update={"title": "Nowy tytuł", "detected_at": later, "updated_at": later,
                "url": "https://example.com/oferta?v=2", "platform": "other"}
    )
    [second] = backend.store.save_findings(doc, [again])
    assert second.outcome == "updated"
    assert second.finding.id == first.finding.id
    assert second.finding.detected_at == first.finding.detected_at
    assert second.finding.score == 0.9
    assert second.finding.title == "Nowy tytuł"
    assert second.finding.updated_at == later
    assert (second.finding.url, second.finding.platform) == ("https://example.com/oferta?v=2", "other")
    assert backend.store.findings_for_document(DOC_ID) == [second.finding]


def test_analyst_status_and_note_survive(backend):
    backend.seed(columns())
    doc = load(backend)
    backend.store.save_findings(doc, [finding()])
    backend.set_status(DOC_ID, "M2", "confirmed", "sprawdzone")
    [saved] = backend.store.save_findings(doc, [finding(score=0.8, fid="55555555-5555-4555-8555-555555555555")])
    assert (saved.finding.status, saved.finding.note) == ("confirmed", "sprawdzone")


def test_changed_page_gets_a_new_finding(backend):
    backend.seed(columns())
    backend.seed(columns(id=DOC2_ID, content_hash=HASH_B))
    [old] = backend.store.save_findings(load(backend), [finding()])
    [new] = backend.store.save_findings(
        load(backend, DOC2_ID), [finding(document_id=DOC2_ID, fid="55555555-5555-4555-8555-555555555555")]
    )
    assert new.outcome == "created"
    assert new.finding.id != old.finding.id
    assert backend.store.findings_for_document(DOC_ID) == [old.finding]


def test_two_modules_two_rows(backend):
    backend.seed(columns())
    saved = backend.store.save_findings(
        load(backend), [finding(module="M1", fid="66666666-6666-4666-8666-666666666666"), finding(module="M2")]
    )
    assert [s.outcome for s in saved] == ["created", "created"]
    assert {f.module for f in backend.store.findings_for_document(DOC_ID)} == {"M1", "M2"}


def test_failure_mid_batch_commits_nothing(backend):
    backend.seed(columns())
    bad = finding(document_id=MISSING_ID, module="M1", fid="66666666-6666-4666-8666-666666666666")
    with pytest.raises(StoreError):
        backend.store.save_findings(load(backend), [finding(), bad])
    assert backend.store.findings_for_document(DOC_ID) == []


def test_concurrent_saves_end_with_one_row(backend):
    backend.seed(columns())
    doc = load(backend)
    backend.widen_race_window()
    results, barrier = [], threading.Barrier(2)

    def save(fid: str) -> None:
        barrier.wait()
        results.extend(backend.store.save_findings(doc, [finding(fid=fid)]))

    threads = [
        threading.Thread(target=save, args=(fid,))
        for fid in ("77777777-7777-4777-8777-777777777777", "88888888-8888-4888-8888-888888888888")
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(r.outcome for r in results) == ["created", "updated"]
    assert len(backend.store.findings_for_document(DOC_ID)) == 1
    assert results[0].finding.id == results[1].finding.id


def test_stored_finding_is_contract_valid(backend, finding_validator):
    backend.seed(columns())
    backend.store.save_findings(load(backend), [finding()])
    [stored] = backend.store.findings_for_document(DOC_ID)
    errors = list(finding_validator.iter_errors(stored.to_contract()))
    assert errors == []


# ---- outage -------------------------------------------------------------------------------------


def test_in_memory_outage_raises_retryable_error_and_writes_nothing():
    store = InMemoryStore()
    store.put_document_row(columns())
    doc = store.load_document(DOC_ID)
    store.unavailable = True
    with pytest.raises(StoreUnavailable):
        store.load_document(DOC_ID)
    with pytest.raises(StoreUnavailable):
        store.save_findings(doc, [finding()])
    store.unavailable = False
    assert store.findings_for_document(DOC_ID) == []


def test_postgres_unreachable_raises_retryable_error():
    store = PostgresStore("postgresql://nobody@127.0.0.1:1/none", connect_timeout=1)
    with pytest.raises(StoreUnavailable):
        store.load_document(DOC_ID)
    with pytest.raises(StoreUnavailable):
        store.save_findings(ScrapedDocument.model_validate(columns()), [finding()])
    store.close()


def test_postgres_error_hides_the_password():
    store = PostgresStore("postgresql://nobody:s3cret-pw@127.0.0.1:1/none", connect_timeout=1)
    with pytest.raises(StoreUnavailable) as err:
        store.load_document(DOC_ID)
    assert "s3cret-pw" not in str(err.value)
    store.close()


def test_postgres_recovers_after_the_connection_drops(pg_url):
    backend = PostgresBackend(pg_url)
    backend.seed(columns())
    assert load(backend).id == DOC_ID
    import psycopg

    with psycopg.connect(pg_url, autocommit=True) as conn:  # kill every other session on this database
        conn.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                     "WHERE datname = current_database() AND pid <> pg_backend_pid()")
    with pytest.raises(StoreUnavailable):
        load(backend)
    assert load(backend).id == DOC_ID  # a new connection on the next call
    backend.close()


class RaisingConn:
    """Stands in for an open psycopg connection whose statement fails."""

    closed = False

    def __init__(self, error: Exception) -> None:
        self.error = error

    def execute(self, *args, **kwargs):
        raise self.error

    def close(self) -> None:
        self.closed = True


@pytest.mark.parametrize("error_name", ["SerializationFailure", "DeadlockDetected"])
def test_postgres_conflict_is_retryable_and_keeps_the_connection(error_name):
    from psycopg import errors

    store = PostgresStore("postgresql://unused@127.0.0.1:1/none")
    conn = RaisingConn(getattr(errors, error_name)("conflict"))
    store._local.conn = conn
    with pytest.raises(StoreUnavailable, match=error_name):
        store.load_document(DOC_ID)
    assert store._local.conn is conn and not conn.closed  # a conflict is not a broken connection


def test_postgres_operational_error_drops_a_still_open_connection():
    from psycopg import errors

    store = PostgresStore("postgresql://unused@127.0.0.1:1/none")
    conn = RaisingConn(errors.QueryCanceled("statement timeout"))  # OperationalError, connection stays open
    store._local.conn = conn
    with pytest.raises(StoreUnavailable):
        store.load_document(DOC_ID)
    assert store._local.conn is None and conn.closed  # the next call opens a fresh connection
