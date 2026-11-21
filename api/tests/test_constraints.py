"""Requirements on columns, dedup, marker, upsert and the side tables (specs/database-schema)."""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from sqlalchemy import func, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError

from dbutil import document_row, finding_row, now, source_row
from investwatch_api.db.sql import findings_upsert, latest_calibration_run, unpublished_documents
from investwatch_api.db.tables import calibration_points, documents, findings, job_errors, sources


def _insert(conn, table, row):
    return conn.execute(insert(table).values(row))


def _add_doc(conn, **over) -> dict:
    row = document_row(**over)
    _insert(conn, documents, row)
    return row


def _insert_ignore(conn, row):
    """What the scraper runs: INSERT ... ON CONFLICT DO NOTHING without a conflict target."""
    return conn.execute(pg_insert(documents).values(row).on_conflict_do_nothing().returning(documents.c.id))


def _count(conn, table) -> int:
    return conn.execute(select(func.count()).select_from(table)).scalar_one()


# --- Documents are deduplicated per source -------------------------------------------------

def test_same_text_from_the_same_source(app_engine):
    with app_engine.begin() as conn:
        src = source_row()
        _insert(conn, sources, src)
        h = "a" * 64
        assert _insert_ignore(conn, document_row(source_id=src["id"], content_hash=h)).fetchone() is not None
        assert _insert_ignore(conn, document_row(source_id=src["id"], content_hash=h)).fetchone() is None
        assert _count(conn, documents) == 1


def test_same_text_from_two_sources(app_engine):
    with app_engine.begin() as conn:
        a, b = source_row(), source_row()
        _insert(conn, sources, a)
        _insert(conn, sources, b)
        _insert_ignore(conn, document_row(source_id=a["id"], content_hash="b" * 64))
        _insert_ignore(conn, document_row(source_id=b["id"], content_hash="b" * 64))
        assert _count(conn, documents) == 2


def test_ad_hoc_documents_without_a_source(app_engine):
    with app_engine.begin() as conn:
        _insert_ignore(conn, document_row(source_id=None, content_hash="c" * 64))
        _insert_ignore(conn, document_row(source_id=None, content_hash="c" * 64))
        assert _count(conn, documents) == 1


def test_documents_without_a_hash(app_engine):
    with app_engine.begin() as conn:
        src = source_row()
        _insert(conn, sources, src)
        _insert_ignore(conn, document_row(source_id=src["id"], content_hash=None))
        _insert_ignore(conn, document_row(source_id=src["id"], content_hash=None))
        assert _count(conn, documents) == 2


def test_unknown_source(app_engine):
    with pytest.raises(IntegrityError, match="foreign key"):
        with app_engine.begin() as conn:
            _add_doc(conn, source_id=uuid.uuid4())


# --- Published-to-stream marker --------------------------------------------------------------

def test_marked_document_leaves_the_sweep(app_engine):
    with app_engine.begin() as conn:
        t = now()
        old = _add_doc(conn, created_at=t - timedelta(minutes=1))
        new = _add_doc(conn, created_at=t)
        assert [r.id for r in conn.execute(unpublished_documents(10))] == [old["id"], new["id"]]
        conn.execute(update(documents).where(documents.c.id == old["id"]).values(stream_published_at=now()))
        assert [r.id for r in conn.execute(unpublished_documents(10))] == [new["id"]]


def test_sweep_returns_oldest_first_up_to_the_limit(app_engine):
    with app_engine.begin() as conn:
        t = now()
        _add_doc(conn, created_at=t)
        early = _add_doc(conn, created_at=t - timedelta(minutes=5))
        assert [r.id for r in conn.execute(unpublished_documents(1))] == [early["id"]]


# --- One finding per document and module -----------------------------------------------------

def test_rescan_of_the_same_document_keeps_analyst_work(app_engine):
    with app_engine.begin() as conn:
        doc = _add_doc(conn)
        first = finding_row(doc["id"], score=0.4, status="in_review", note="sprawdzam", title="stary")
        conn.execute(findings_upsert(first))
        later = now() + timedelta(minutes=1)
        rescan = finding_row(doc["id"], score=0.9, status="new", note=None, detected_at=later, updated_at=later,
                             title="nowy", summary="s", content_excerpt="e", firm={"name": "Alfa"},
                             advertiser={"name": "Jan"}, model={"pipeline_version": "0.2.0"},
                             rules=[{"rule_id": "R3", "name": "Ryzyko", "result": "fail", "severity": "high"}])
        conn.execute(findings_upsert(rescan))
        rows = conn.execute(select(findings)).mappings().all()
        assert len(rows) == 1
        row = rows[0]
        assert (row["id"], row["detected_at"], row["status"], row["note"]) == (
            first["id"], first["detected_at"], "in_review", "sprawdzam")
        assert (row["score"], row["title"], row["summary"], row["content_excerpt"]) == (0.9, "nowy", "s", "e")
        assert (row["firm"], row["advertiser"], row["model"]) == (
            {"name": "Alfa"}, {"name": "Jan"}, {"pipeline_version": "0.2.0"})
        assert row["rules"][0]["rule_id"] == "R3"
        assert row["updated_at"] == later


def test_different_modules_on_one_document(app_engine):
    with app_engine.begin() as conn:
        doc = _add_doc(conn)
        conn.execute(findings_upsert(finding_row(doc["id"], module="M1")))
        conn.execute(findings_upsert(finding_row(doc["id"], module="M2")))
        assert _count(conn, findings) == 2


def test_plain_duplicate_insert_is_rejected(app_engine):
    with pytest.raises(IntegrityError, match="uq_findings_document_module"):
        with app_engine.begin() as conn:
            doc = _add_doc(conn)
            _insert(conn, findings, finding_row(doc["id"]))
            _insert(conn, findings, finding_row(doc["id"]))


def test_finding_for_a_missing_document(app_engine):
    with pytest.raises(IntegrityError, match="foreign key"):
        with app_engine.begin() as conn:
            _insert(conn, findings, finding_row(uuid.uuid4()))


# --- Columns follow the contracts ------------------------------------------------------------

@pytest.mark.parametrize("table, over", [
    ("documents", {"platform": "myspace"}),
    ("documents", {"source_kind": "partner"}),
    ("documents", {"lang": "POL"}),
    ("documents", {"content_hash": "XYZ"}),
    ("documents", {"http_status": 99}),
    ("documents", {"http_status": 600}),
    ("findings", {"module": "M4"}),
    ("findings", {"status": "archived"}),
    ("findings", {"platform": "myspace"}),
    ("findings", {"score": 1.2}),
    ("findings", {"score": -0.1}),
    ("findings", {"content_excerpt": "x" * 501}),
    ("sources", {"platform": "myspace"}),
    ("sources", {"source_kind": "partner"}),
    ("sources", {"target_modules": []}),
    ("sources", {"target_modules": ["M4"]}),
    ("sources", {"last_run_status": "done"}),
    ("sources", {"name": ""}),
])
def test_out_of_contract_value_is_rejected(app_engine, table, over):
    with pytest.raises(IntegrityError, match="check constraint"):
        with app_engine.begin() as conn:
            if table == "documents":
                _add_doc(conn, **over)
            elif table == "findings":
                doc = _add_doc(conn)
                _insert(conn, findings, finding_row(doc["id"], **over))
            else:
                _insert(conn, sources, source_row(**over))
    with app_engine.connect() as conn:
        assert _count(conn, findings) == 0 and _count(conn, sources) == 0


@pytest.mark.parametrize("over", [{"score": 0.0}, {"score": 1.0}, {"content_excerpt": "x" * 500}])
def test_contract_boundaries_are_allowed(app_engine, over):
    with app_engine.begin() as conn:
        doc = _add_doc(conn, http_status=100, lang="pl")
        _add_doc(conn, http_status=599)
        _insert(conn, findings, finding_row(doc["id"], **over))
        _insert(conn, sources, source_row(target_modules=["M1", "M2", "M3"], last_run_status="running"))


@pytest.mark.parametrize("missing", ["text", "url", "platform", "source_kind", "fetched_at"])
def test_required_document_field_missing(app_engine, missing):
    with pytest.raises(IntegrityError, match="not-null"):
        with app_engine.begin() as conn:
            row = document_row()
            row[missing] = None
            _insert(conn, documents, row)


def test_finding_has_no_risk_level_column():
    assert "risk_level" not in findings.c


# --- Job errors and calibration points -------------------------------------------------------

def test_job_error_is_recorded_and_read_newest_first(app_engine):
    with app_engine.begin() as conn:
        src = source_row()
        _insert(conn, sources, src)
        t = now()
        for i, reason in enumerate(("timeout", "blocked")):
            _insert(conn, job_errors, dict(id=uuid.uuid4(), source_id=src["id"], url=src["url"], reason=reason,
                                           occurred_at=t + timedelta(seconds=i)))
        q = select(job_errors.c.reason).where(job_errors.c.source_id == src["id"]).order_by(
            job_errors.c.occurred_at.desc())
        assert conn.execute(q).scalars().all() == ["blocked", "timeout"]


def test_job_errors_have_no_secret_columns():
    assert set(job_errors.c.keys()) == {"id", "source_id", "url", "reason", "detail", "occurred_at"}


def test_empty_reason_is_rejected(app_engine):
    with pytest.raises(IntegrityError, match="check constraint"):
        with app_engine.begin() as conn:
            _insert(conn, job_errors, dict(id=uuid.uuid4(), reason=""))


def _point(run_id, threshold, computed_at, module="M2"):
    return dict(run_id=run_id, module=module, threshold=threshold, tp=1, fp=1, fn=1, tn=1, precision=0.5,
                recall=0.5, labeled_samples=4, computed_at=computed_at)


def test_latest_calibration_run_per_module(app_engine):
    with app_engine.begin() as conn:
        old_run, new_run, t = uuid.uuid4(), uuid.uuid4(), now()
        for th in (0.5, 0.3):
            _insert(conn, calibration_points, _point(old_run, th, t - timedelta(hours=1)))
        for th in (0.7, 0.4):
            _insert(conn, calibration_points, _point(new_run, th, t))
        _insert(conn, calibration_points, _point(uuid.uuid4(), 0.5, t + timedelta(hours=1), module="M1"))
        rows = conn.execute(latest_calibration_run("M2")).mappings().all()
        assert [r["threshold"] for r in rows] == [0.4, 0.7]
        assert {r["run_id"] for r in rows} == {new_run}


def test_duplicate_point_in_one_run(app_engine):
    with pytest.raises(IntegrityError, match="uq_calibration_points_run_module_threshold"):
        with app_engine.begin() as conn:
            run, t = uuid.uuid4(), now()
            _insert(conn, calibration_points, _point(run, 0.5, t))
            _insert(conn, calibration_points, _point(run, 0.5, t))
