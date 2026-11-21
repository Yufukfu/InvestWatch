"""finding-storage scenarios (openspec/changes/analytics-worker/specs/finding-storage/spec.md).

The suite runs on every store backend in STORE_BACKENDS; the Postgres backend joins in task group 2
and is skipped without TEST_DATABASE_URL.
"""

from __future__ import annotations

import threading
import time
from datetime import timedelta

import pytest

from conftest import NOW, make_doc
from investwatch_analytics.models import Finding, ScrapedDocument
from investwatch_analytics.storage import InMemoryStore, InvalidDocument, NotFound, StoreUnavailable

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


STORE_BACKENDS = [InMemoryBackend]


@pytest.fixture(params=STORE_BACKENDS, ids=lambda b: b.__name__)
def backend(request):
    return request.param()


def columns(**overrides) -> dict:
    doc = make_doc(id=DOC_ID, title="Konto Premium", content_hash="abc")
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


def test_load_invalid_row_names_the_field(backend):
    backend.seed(columns(text=None))
    with pytest.raises(InvalidDocument) as err:
        load(backend)
    assert err.value.field == "text"


def test_load_bad_enum_names_the_field(backend):
    backend.seed(columns(source_kind="partner"))
    with pytest.raises(InvalidDocument) as err:
        load(backend)
    assert err.value.field == "source_kind"


# ---- save ---------------------------------------------------------------------------------------


def test_first_analysis_inserts_with_status_new(backend):
    backend.seed(columns())
    doc = load(backend)
    [saved] = backend.store.save_findings(doc, [finding()])
    assert saved.outcome == "created"
    assert saved.finding.status == "new"
    assert saved.finding.id == "44444444-4444-4444-8444-444444444444"
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
        update={"title": "Nowy tytuł", "detected_at": later, "updated_at": later}
    )
    [second] = backend.store.save_findings(doc, [again])
    assert second.outcome == "updated"
    assert second.finding.id == first.finding.id
    assert second.finding.detected_at == first.finding.detected_at
    assert second.finding.score == 0.9
    assert second.finding.title == "Nowy tytuł"
    assert second.finding.updated_at == later
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
    backend.seed(columns(id=DOC2_ID, content_hash="def"))
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
    with pytest.raises(Exception):
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
