"""The statements other services rely on (copied verbatim into api/README.md for the scraper and analytics)."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import Select, func, select
from sqlalchemy.dialects.postgresql import Insert, insert

from .tables import calibration_points, documents, findings

# Fields a re-scan replaces. id, document_id, module, detected_at, status and note are kept:
# analytics never changes an analyst's status or note.
UPSERT_REPLACED = ("score", "title", "summary", "firm", "advertiser", "rules", "content_excerpt", "url",
                   "platform", "model", "updated_at")


def document_insert_ignore_duplicate(row: dict) -> Insert:
    """Scraper insert. Only a (source_id, content_hash) duplicate is dropped (RETURNING gives no row);
    any other conflict, such as a reused id, still raises instead of silently losing the document."""
    return (insert(documents).values(row)
            .on_conflict_do_nothing(index_elements=["source_id", "content_hash"],
                                    index_where=documents.c.content_hash.isnot(None))
            .returning(documents.c.id))


def findings_upsert(row: dict) -> Insert:
    stmt = insert(findings).values(row)
    return stmt.on_conflict_do_update(
        constraint="uq_findings_document_module",
        set_={name: stmt.excluded[name] for name in UPSERT_REPLACED},
    )


def unpublished_documents(limit: int, older_than: timedelta = timedelta(0)) -> Select:
    """Republish sweep: documents not yet announced on iw:documents, oldest first.

    `older_than` skips rows that a running ingest has just committed and is about to announce itself
    (the scraper uses about a minute), so the sweep does not double-publish them in the normal case.
    """
    query = select(documents.c.id).where(documents.c.stream_published_at.is_(None))
    if older_than > timedelta(0):
        query = query.where(documents.c.created_at < func.now() - older_than)
    return query.order_by(documents.c.created_at, documents.c.id).limit(limit)


def latest_calibration_run(module: str) -> Select:
    """Points of the newest calibration run of one module, by ascending threshold.
    Ties on computed_at resolve to the greatest run_id, so the pick is stable."""
    latest = (select(calibration_points.c.run_id)
              .where(calibration_points.c.module == module)
              .order_by(calibration_points.c.computed_at.desc(), calibration_points.c.run_id.desc())
              .limit(1)
              .scalar_subquery())
    return (select(calibration_points)
            .where(calibration_points.c.module == module, calibration_points.c.run_id == latest)
            .order_by(calibration_points.c.threshold))
