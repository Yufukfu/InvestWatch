"""initial shared tables: sources, documents, findings, job_errors, calibration_points

Revision ID: 0001
Revises:
Create Date: 2026-11-21

Written by hand from investwatch_api/db/tables.py; `alembic check` (tests/test_migrations.py) proves they match.
Never edit this revision after it is applied: add a new one.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

PLATFORMS = "('web', 'facebook', 'instagram', 'tiktok', 'youtube', 'x', 'forum', 'other')"
SOURCE_KINDS = "('firm_own', 'third_party', 'unknown')"
MODULES = "('M1', 'M2', 'M3')"
STATUSES = "('new', 'in_review', 'confirmed', 'false_positive', 'closed')"
RUN_STATUSES = "('ok', 'partial', 'failed', 'running')"


def _tz(name: str, **kw) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), **kw)


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("platform", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("source_kind", sa.Text(), nullable=False),
        sa.Column("target_modules", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("schedule_cron", sa.Text()),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        _tz("last_run_at"),
        sa.Column("last_run_status", sa.Text()),
        _tz("created_at", server_default=sa.func.now(), nullable=False),
        _tz("updated_at", server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_sources"),
        sa.CheckConstraint("name <> ''", name="ck_sources_name_not_empty"),
        sa.CheckConstraint(f"platform IN {PLATFORMS}", name="ck_sources_platform"),
        sa.CheckConstraint(f"source_kind IN {SOURCE_KINDS}", name="ck_sources_source_kind"),
        sa.CheckConstraint("cardinality(target_modules) >= 1 AND target_modules <@ ARRAY['M1','M2','M3']::text[]",
                           name="ck_sources_target_modules"),
        sa.CheckConstraint(f"last_run_status IN {RUN_STATUSES}", name="ck_sources_last_run_status"),
    )

    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid()),
        sa.Column("platform", sa.Text(), nullable=False),
        sa.Column("source_kind", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("canonical_url", sa.Text()),
        _tz("fetched_at", nullable=False),
        _tz("published_at"),
        sa.Column("http_status", sa.Integer()),
        sa.Column("lang", sa.Text()),
        sa.Column("title", sa.Text()),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.Text()),
        sa.Column("html_object_key", sa.Text()),
        sa.Column("payload", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        _tz("stream_published_at"),
        _tz("created_at", server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_documents"),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], name="fk_documents_source_id"),
        sa.CheckConstraint(f"platform IN {PLATFORMS}", name="ck_documents_platform"),
        sa.CheckConstraint(f"source_kind IN {SOURCE_KINDS}", name="ck_documents_source_kind"),
        sa.CheckConstraint("http_status BETWEEN 100 AND 599", name="ck_documents_http_status"),
        sa.CheckConstraint("lang ~ '^[a-z]{2}$'", name="ck_documents_lang"),
        sa.CheckConstraint("content_hash ~ '^[a-f0-9]{64}$'", name="ck_documents_content_hash"),
        sa.CheckConstraint("jsonb_typeof(payload) = 'object'", name="ck_documents_payload_object"),
    )
    # Dedup (ADR 0307): one row per (source, text); ad-hoc documents (no source) dedup too; rows without
    # a hash never collide. The scraper inserts with ON CONFLICT DO NOTHING (no conflict target needed).
    op.create_index("uq_documents_source_hash", "documents", ["source_id", "content_hash"], unique=True,
                    postgresql_nulls_not_distinct=True, postgresql_where=sa.text("content_hash IS NOT NULL"))
    op.create_index("ix_documents_unpublished", "documents", ["created_at"],
                    postgresql_where=sa.text("stream_published_at IS NULL"))

    op.create_table(
        "findings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("module", sa.Text(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'new'"), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text()),
        sa.Column("firm", postgresql.JSONB()),
        sa.Column("advertiser", postgresql.JSONB()),
        sa.Column("rules", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("content_excerpt", sa.Text()),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("platform", sa.Text(), nullable=False),
        sa.Column("note", sa.Text()),
        _tz("detected_at", nullable=False),
        _tz("updated_at", nullable=False),
        sa.Column("model", postgresql.JSONB()),
        sa.PrimaryKeyConstraint("id", name="pk_findings"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], name="fk_findings_document_id",
                                ondelete="CASCADE"),
        sa.UniqueConstraint("document_id", "module", name="uq_findings_document_module"),
        sa.CheckConstraint(f"module IN {MODULES}", name="ck_findings_module"),
        sa.CheckConstraint("score >= 0 AND score <= 1", name="ck_findings_score"),
        sa.CheckConstraint(f"status IN {STATUSES}", name="ck_findings_status"),
        sa.CheckConstraint(f"platform IN {PLATFORMS}", name="ck_findings_platform"),
        sa.CheckConstraint("char_length(content_excerpt) <= 500", name="ck_findings_content_excerpt"),
        sa.CheckConstraint("jsonb_typeof(rules) = 'array'", name="ck_findings_rules_array"),
    )

    op.create_table(
        "job_errors",
        sa.Column("id", sa.Uuid(), nullable=False),
        # No foreign key on purpose: the scraper records errors for scan requests naming unknown sources.
        sa.Column("source_id", sa.Uuid()),
        sa.Column("url", sa.Text()),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("detail", sa.Text()),
        _tz("occurred_at", server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_job_errors"),
        sa.CheckConstraint("reason <> ''", name="ck_job_errors_reason_not_empty"),
    )

    op.create_table(
        "calibration_points",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("module", sa.Text(), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=False),
        sa.Column("tp", sa.Integer(), nullable=False),
        sa.Column("fp", sa.Integer(), nullable=False),
        sa.Column("fn", sa.Integer(), nullable=False),
        sa.Column("tn", sa.Integer(), nullable=False),
        sa.Column("precision", sa.Float(), nullable=False),
        sa.Column("recall", sa.Float(), nullable=False),
        sa.Column("f1", sa.Float()),
        sa.Column("labeled_samples", sa.Integer(), nullable=False),
        _tz("computed_at", nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_calibration_points"),
        sa.UniqueConstraint("run_id", "module", "threshold", name="uq_calibration_points_run_module_threshold"),
        sa.CheckConstraint(f"module IN {MODULES}", name="ck_calibration_points_module"),
        sa.CheckConstraint("threshold >= 0 AND threshold <= 1", name="ck_calibration_points_threshold"),
        sa.CheckConstraint("tp >= 0 AND fp >= 0 AND fn >= 0 AND tn >= 0 AND labeled_samples >= 0",
                           name="ck_calibration_points_counts"),
    )
    op.create_index("ix_calibration_points_module_computed_at", "calibration_points",
                    ["module", sa.text("computed_at DESC")])

    # Default privileges (infra/postgres/init/01-app-role.sh) also gave the app role CRUD on alembic_version.
    # Only the admin role may move the schema version.
    op.execute("""
        DO $$
        DECLARE r record;
        BEGIN
          FOR r IN SELECT DISTINCT grantee FROM information_schema.role_table_grants
                   WHERE table_schema = 'public' AND table_name = 'alembic_version'
                     AND grantee NOT IN (current_user, 'PUBLIC')
          LOOP
            EXECUTE format('REVOKE ALL ON TABLE public.alembic_version FROM %I', r.grantee);
          END LOOP;
        END $$;
    """)


def downgrade() -> None:
    op.drop_table("calibration_points")
    op.drop_table("job_errors")
    op.drop_table("findings")
    op.drop_table("documents")
    op.drop_table("sources")
