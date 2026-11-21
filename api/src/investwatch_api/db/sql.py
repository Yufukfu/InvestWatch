"""The statements other services rely on (copied verbatim into api/README.md for the scraper and analytics)."""

from __future__ import annotations

from sqlalchemy import Select, select
from sqlalchemy.dialects.postgresql import Insert, insert

from .tables import calibration_points, documents, findings

# Fields a re-scan replaces. id, document_id, module, detected_at, status and note are kept:
# analytics never changes an analyst's status or note.
UPSERT_REPLACED = ("score", "title", "summary", "firm", "advertiser", "rules", "content_excerpt", "url",
                   "platform", "model", "updated_at")


def findings_upsert(row: dict) -> Insert:
    stmt = insert(findings).values(row)
    return stmt.on_conflict_do_update(
        constraint="uq_findings_document_module",
        set_={name: stmt.excluded[name] for name in UPSERT_REPLACED},
    )


def unpublished_documents(limit: int) -> Select:
    """Republish sweep: documents not yet announced on iw:documents, oldest first."""
    return (select(documents.c.id)
            .where(documents.c.stream_published_at.is_(None))
            .order_by(documents.c.created_at, documents.c.id)
            .limit(limit))


def latest_calibration_run(module: str) -> Select:
    """Points of the newest calibration run of one module, by ascending threshold."""
    latest = (select(calibration_points.c.run_id)
              .where(calibration_points.c.module == module)
              .order_by(calibration_points.c.computed_at.desc())
              .limit(1)
              .scalar_subquery())
    return (select(calibration_points)
            .where(calibration_points.c.module == module, calibration_points.c.run_id == latest)
            .order_by(calibration_points.c.threshold))

