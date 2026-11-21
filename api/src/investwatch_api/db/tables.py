"""Shared tables as SQLAlchemy Core (ADR 0307). The schema itself is created only by Alembic revisions.

Allowed values come from contracts/schemas/ (v1). Enumerations are text + CHECK, not Postgres ENUMs,
so a value can be added or removed in one revision.
"""

from __future__ import annotations

from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Identity,
    Index,
    BigInteger,
    Integer,
    MetaData,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

PLATFORMS = ("web", "facebook", "instagram", "tiktok", "youtube", "x", "forum", "other")
SOURCE_KINDS = ("firm_own", "third_party", "unknown")
MODULES = ("M1", "M2", "M3")
STATUSES = ("new", "in_review", "confirmed", "false_positive", "closed")
RUN_STATUSES = ("ok", "partial", "failed", "running")

# Constraint names are fixed so revisions and error messages stay stable.
metadata = MetaData(naming_convention={
    "pk": "pk_%(table_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
})


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _tz(name: str, **kw) -> Column:
    return Column(name, DateTime(timezone=True), **kw)


sources = Table(
    "sources", metadata,
    Column("id", Uuid, primary_key=True),
    Column("name", Text, nullable=False),
    Column("platform", Text, nullable=False),
    Column("url", Text, nullable=False),
    Column("source_kind", Text, nullable=False),
    Column("target_modules", ARRAY(Text), nullable=False),
    Column("schedule_cron", Text),
    Column("active", Boolean, nullable=False, server_default=text("true")),
    _tz("last_run_at"),
    Column("last_run_status", Text),
    _tz("created_at", nullable=False, server_default=func.now()),
    _tz("updated_at", nullable=False, server_default=func.now()),
    CheckConstraint("name <> ''", name="name_not_empty"),
    CheckConstraint(_in("platform", PLATFORMS), name="platform"),
    CheckConstraint(_in("source_kind", SOURCE_KINDS), name="source_kind"),
    CheckConstraint("cardinality(target_modules) >= 1 AND target_modules <@ ARRAY['M1','M2','M3']::text[]",
                    name="target_modules"),
    CheckConstraint(_in("last_run_status", RUN_STATUSES), name="last_run_status"),
)

documents = Table(
    "documents", metadata,
    Column("id", Uuid, primary_key=True),
    Column("source_id", Uuid, ForeignKey("sources.id")),
    Column("platform", Text, nullable=False),
    Column("source_kind", Text, nullable=False),
    Column("url", Text, nullable=False),
    Column("canonical_url", Text),
    _tz("fetched_at", nullable=False),
    _tz("published_at"),
    Column("http_status", Integer),
    Column("lang", Text),
    Column("title", Text),
    Column("text", Text, nullable=False),
    Column("content_hash", Text),
    Column("html_object_key", Text),
    # author, links, media, screenshots, blocks, scrape_meta (integration-plan §3)
    Column("payload", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    # set once the document is announced on Redis Stream iw:documents; not the contract's published_at
    _tz("stream_published_at"),
    _tz("created_at", nullable=False, server_default=func.now()),
    CheckConstraint(_in("platform", PLATFORMS), name="platform"),
    CheckConstraint(_in("source_kind", SOURCE_KINDS), name="source_kind"),
    CheckConstraint("http_status BETWEEN 100 AND 599", name="http_status"),
    CheckConstraint("lang ~ '^[a-z]{2}$'", name="lang"),
    CheckConstraint("content_hash ~ '^[a-f0-9]{64}$'", name="content_hash"),
    CheckConstraint("jsonb_typeof(payload) = 'object'", name="payload_object"),
    CheckConstraint("text <> ''", name="text_not_empty"),  # revision 0003
)
Index("uq_documents_source_hash", documents.c.source_id, documents.c.content_hash, unique=True,
      postgresql_nulls_not_distinct=True, postgresql_where=documents.c.content_hash.isnot(None))
Index("ix_documents_unpublished", documents.c.created_at,
      postgresql_where=documents.c.stream_published_at.is_(None))

findings = Table(
    "findings", metadata,
    Column("id", Uuid, primary_key=True),
    Column("document_id", Uuid, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
    Column("module", Text, nullable=False),
    Column("score", Float, nullable=False),
    Column("status", Text, nullable=False, server_default=text("'new'")),
    Column("title", Text, nullable=False),
    Column("summary", Text),
    # none_as_null: a contract null is SQL NULL, so `IS NULL` filters work (JSON null would not match)
    Column("firm", JSONB(none_as_null=True)),
    Column("advertiser", JSONB(none_as_null=True)),
    Column("rules", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
    Column("content_excerpt", Text),
    Column("url", Text, nullable=False),
    Column("platform", Text, nullable=False),
    Column("note", Text),
    _tz("detected_at", nullable=False),
    _tz("updated_at", nullable=False),
    Column("model", JSONB(none_as_null=True)),
    UniqueConstraint("document_id", "module", name="uq_findings_document_module"),
    CheckConstraint(_in("module", MODULES), name="module"),
    CheckConstraint("score >= 0 AND score <= 1", name="score"),
    CheckConstraint(_in("status", STATUSES), name="status"),
    CheckConstraint(_in("platform", PLATFORMS), name="platform"),
    CheckConstraint("char_length(content_excerpt) <= 500", name="content_excerpt"),
    CheckConstraint("jsonb_typeof(rules) = 'array'", name="rules_array"),
)
# Revision 0002: GET /findings filters and default sort, /stats/trend.
Index("ix_findings_detected_at", findings.c.detected_at.desc())
Index("ix_findings_module", findings.c.module, findings.c.detected_at.desc())
Index("ix_findings_status", findings.c.status)
Index("ix_findings_platform", findings.c.platform)
Index("ix_findings_score", findings.c.score)

job_errors = Table(
    "job_errors", metadata,
    Column("id", Uuid, primary_key=True),
    Column("source_id", Uuid),  # no FK: errors for scan requests naming unknown sources are kept
    Column("url", Text),
    Column("reason", Text, nullable=False),
    Column("detail", Text),
    _tz("occurred_at", nullable=False, server_default=func.now()),
    CheckConstraint("reason <> ''", name="reason_not_empty"),
)
Index("ix_job_errors_source_id_occurred_at", job_errors.c.source_id, job_errors.c.occurred_at.desc())

calibration_points = Table(
    "calibration_points", metadata,
    Column("id", BigInteger, Identity(always=False), primary_key=True),
    Column("run_id", Uuid, nullable=False),
    Column("module", Text, nullable=False),
    Column("threshold", Float, nullable=False),
    Column("tp", Integer, nullable=False),
    Column("fp", Integer, nullable=False),
    Column("fn", Integer, nullable=False),
    Column("tn", Integer, nullable=False),
    Column("precision", Float, nullable=False),
    Column("recall", Float, nullable=False),
    Column("f1", Float),
    Column("labeled_samples", Integer, nullable=False),
    _tz("computed_at", nullable=False),
    UniqueConstraint("run_id", "module", "threshold", name="uq_calibration_points_run_module_threshold"),
    CheckConstraint(_in("module", MODULES), name="module"),
    CheckConstraint("threshold >= 0 AND threshold <= 1", name="threshold"),
    CheckConstraint("tp >= 0 AND fp >= 0 AND fn >= 0 AND tn >= 0 AND labeled_samples >= 0", name="counts"),
)
Index("ix_calibration_points_module_computed_at", calibration_points.c.module,
      calibration_points.c.computed_at.desc())
