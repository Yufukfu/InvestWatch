"""Requirement 'Indexes for the dashboard queries' and scenario 'Sweep query uses the index'."""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import inspect, select, text

from investwatch_api.db.sql import unpublished_documents
from investwatch_api.db.tables import findings


def _plan(conn, stmt) -> str:
    """EXPLAIN the statement as SQLAlchemy compiles it for this connection, bound parameters included."""
    conn.execute(text("ANALYZE"))
    compiled = stmt.compile(conn)
    return "\n".join(r[0] for r in conn.exec_driver_sql("EXPLAIN " + compiled.string, compiled.params))


SEED_DOCS = """
INSERT INTO documents (id, platform, source_kind, url, fetched_at, text, stream_published_at, created_at)
SELECT gen_random_uuid(), 'web', 'unknown', 'https://a.example/' || g, now(), 't',
       CASE WHEN g <= :unpublished THEN NULL ELSE now() END, now() - g * interval '1 second'
FROM generate_series(1, :n) AS g
"""

SEED_FINDINGS = """
INSERT INTO findings (id, document_id, module, score, title, url, platform, detected_at, updated_at, status)
SELECT gen_random_uuid(), d.id, (ARRAY['M1','M2','M3'])[1 + (row_number() OVER () % 3)], random(), 't',
       d.url, 'web', now() - row_number() OVER () * interval '1 minute', now(),
       (ARRAY['new','in_review','confirmed','false_positive','closed'])[1 + (row_number() OVER () % 5)]
FROM documents d
"""


@pytest.mark.parametrize("older_than", [timedelta(0), timedelta(minutes=1)])
def test_sweep_query_uses_the_partial_index(app_engine, older_than):
    """The statement from sql.py, so a change there that loses the index turns this red."""
    with app_engine.begin() as conn:
        conn.execute(text(SEED_DOCS), {"n": 10_010, "unpublished": 10})
        plan = _plan(conn, unpublished_documents(100, older_than))
        assert "ix_documents_unpublished" in plan, plan


def test_default_list_query_uses_an_index(app_engine):
    with app_engine.begin() as conn:
        conn.execute(text(SEED_DOCS), {"n": 10_000, "unpublished": 0})
        conn.execute(text(SEED_FINDINGS))
        # sql.py has no findings page statement yet (api-v1 adds the REST query); this is its default shape.
        plan = _plan(conn, select(findings.c.id).order_by(findings.c.detected_at.desc()).limit(50))
        assert "ix_findings_detected_at" in plan, plan
        assert "Seq Scan" not in plan, plan


def _db_indexes(engine, table: str) -> set[tuple[str, ...]]:
    """Columns of every index the migrations created on the table (not tables.py)."""
    return {tuple(ix["column_names"]) for ix in inspect(engine).get_indexes(table)}


@pytest.mark.parametrize("columns", [("detected_at",), ("module",), ("status",), ("platform",), ("score",)])
def test_migrated_findings_filter_columns_are_indexed(app_engine, columns):
    indexed = _db_indexes(app_engine, "findings")
    assert any(ix[: len(columns)] == columns for ix in indexed), indexed


def test_migrated_job_errors_are_indexed_by_source_and_time(app_engine):
    assert ("source_id", "occurred_at") in _db_indexes(app_engine, "job_errors")
