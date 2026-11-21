"""Requirement 'Indexes for the dashboard queries' and scenario 'Sweep query uses the index'."""

from __future__ import annotations

import pytest
from sqlalchemy import text

from investwatch_api.db.tables import findings, job_errors


def _plan(conn, sql: str) -> str:
    conn.execute(text("ANALYZE"))
    return "\n".join(r[0] for r in conn.execute(text("EXPLAIN " + sql)))


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


def test_sweep_query_uses_the_partial_index(app_engine):
    with app_engine.begin() as conn:
        conn.execute(text(SEED_DOCS), {"n": 10_010, "unpublished": 10})
        plan = _plan(conn, "SELECT id FROM documents WHERE stream_published_at IS NULL ORDER BY created_at LIMIT 100")
        assert "ix_documents_unpublished" in plan, plan


def test_default_list_query_uses_an_index(app_engine):
    with app_engine.begin() as conn:
        conn.execute(text(SEED_DOCS), {"n": 10_000, "unpublished": 0})
        conn.execute(text(SEED_FINDINGS))
        plan = _plan(conn, "SELECT id FROM findings ORDER BY detected_at DESC LIMIT 50")
        assert "ix_findings_detected_at" in plan, plan
        assert "Seq Scan" not in plan, plan


@pytest.mark.parametrize("columns", [("detected_at",), ("module",), ("status",), ("platform",), ("score",)])
def test_findings_filter_columns_are_indexed(columns):
    indexed = {tuple(c.name for c in ix.columns) for ix in findings.indexes}
    assert columns in indexed or any(ix[: len(columns)] == columns for ix in indexed)


def test_job_errors_are_indexed_by_source_and_time():
    indexed = {tuple(c.name for c in ix.columns) for ix in job_errors.indexes}
    assert ("source_id", "occurred_at") in indexed
