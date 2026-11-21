-- TEST-ONLY FIXTURE. Never run in compose or against a shared database.
--
-- Mirrors the tables analytics touches from the API's Alembic migrations (change `api-db-schema`,
-- `origin/api/api-db-schema` at 7af51ab, PR #15): `api/migrations/versions/0001_initial.py` (sources,
-- documents, findings), the findings indexes of `0002_query_indexes.py` and the `documents.text` check of
-- `0003_documents_text_not_empty.py`. Column names, types, nullability, defaults and checks are copied as
-- they are. job_errors and calibration_points are left out.
-- Constraint names: the API's naming convention double-prefixes the 0001 CHECK names in a real database
-- (`ck_findings_ck_findings_status`); this file keeps the names as written in 0001. Analytics depends on no
-- constraint name except the upsert target `uq_findings_document_module`, which is the same in both.
-- A missing firm / advertiser / model is SQL NULL, never JSON 'null' (api README).
-- The migrations in api/ are the source of truth (ADR 0303): when they change, update this file and
-- re-run the Postgres store tests (TEST_DATABASE_URL).

CREATE TABLE sources (
    id uuid NOT NULL,
    name text NOT NULL,
    platform text NOT NULL,
    url text NOT NULL,
    source_kind text NOT NULL,
    target_modules text[] NOT NULL,
    schedule_cron text,
    active boolean DEFAULT true NOT NULL,
    last_run_at timestamptz,
    last_run_status text,
    created_at timestamptz DEFAULT now() NOT NULL,
    updated_at timestamptz DEFAULT now() NOT NULL,
    CONSTRAINT pk_sources PRIMARY KEY (id),
    CONSTRAINT ck_sources_name_not_empty CHECK (name <> ''),
    CONSTRAINT ck_sources_platform CHECK (platform IN ('web', 'facebook', 'instagram', 'tiktok', 'youtube', 'x', 'forum', 'other')),
    CONSTRAINT ck_sources_source_kind CHECK (source_kind IN ('firm_own', 'third_party', 'unknown')),
    CONSTRAINT ck_sources_target_modules CHECK (cardinality(target_modules) >= 1 AND target_modules <@ ARRAY['M1','M2','M3']::text[]),
    CONSTRAINT ck_sources_last_run_status CHECK (last_run_status IN ('ok', 'partial', 'failed', 'running'))
);

CREATE TABLE documents (
    id uuid NOT NULL,
    source_id uuid,
    platform text NOT NULL,
    source_kind text NOT NULL,
    url text NOT NULL,
    canonical_url text,
    fetched_at timestamptz NOT NULL,
    published_at timestamptz,
    http_status integer,
    lang text,
    title text,
    text text NOT NULL,
    content_hash text,
    html_object_key text,
    payload jsonb DEFAULT '{}'::jsonb NOT NULL,
    stream_published_at timestamptz,
    created_at timestamptz DEFAULT now() NOT NULL,
    CONSTRAINT pk_documents PRIMARY KEY (id),
    CONSTRAINT fk_documents_source_id FOREIGN KEY (source_id) REFERENCES sources (id),
    CONSTRAINT ck_documents_platform CHECK (platform IN ('web', 'facebook', 'instagram', 'tiktok', 'youtube', 'x', 'forum', 'other')),
    CONSTRAINT ck_documents_source_kind CHECK (source_kind IN ('firm_own', 'third_party', 'unknown')),
    CONSTRAINT ck_documents_http_status CHECK (http_status BETWEEN 100 AND 599),
    CONSTRAINT ck_documents_lang CHECK (lang ~ '^[a-z]{2}$'),
    CONSTRAINT ck_documents_content_hash CHECK (content_hash ~ '^[a-f0-9]{64}$'),
    CONSTRAINT ck_documents_payload_object CHECK (jsonb_typeof(payload) = 'object'),
    CONSTRAINT ck_documents_text_not_empty CHECK (text <> '')  -- revision 0003
);
CREATE UNIQUE INDEX uq_documents_source_hash ON documents (source_id, content_hash) NULLS NOT DISTINCT
    WHERE content_hash IS NOT NULL;
CREATE INDEX ix_documents_unpublished ON documents (created_at) WHERE stream_published_at IS NULL;

CREATE TABLE findings (
    id uuid NOT NULL,
    document_id uuid NOT NULL,
    module text NOT NULL,
    score double precision NOT NULL,
    status text DEFAULT 'new' NOT NULL,
    title text NOT NULL,
    summary text,
    firm jsonb,
    advertiser jsonb,
    rules jsonb DEFAULT '[]'::jsonb NOT NULL,
    content_excerpt text,
    url text NOT NULL,
    platform text NOT NULL,
    note text,
    detected_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    model jsonb,
    CONSTRAINT pk_findings PRIMARY KEY (id),
    CONSTRAINT fk_findings_document_id FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE,
    CONSTRAINT uq_findings_document_module UNIQUE (document_id, module),
    CONSTRAINT ck_findings_module CHECK (module IN ('M1', 'M2', 'M3')),
    CONSTRAINT ck_findings_score CHECK (score >= 0 AND score <= 1),
    CONSTRAINT ck_findings_status CHECK (status IN ('new', 'in_review', 'confirmed', 'false_positive', 'closed')),
    CONSTRAINT ck_findings_platform CHECK (platform IN ('web', 'facebook', 'instagram', 'tiktok', 'youtube', 'x', 'forum', 'other')),
    CONSTRAINT ck_findings_content_excerpt CHECK (char_length(content_excerpt) <= 500),
    CONSTRAINT ck_findings_rules_array CHECK (jsonb_typeof(rules) = 'array')
);
CREATE INDEX ix_findings_detected_at ON findings (detected_at DESC);
CREATE INDEX ix_findings_module ON findings (module, detected_at DESC);
CREATE INDEX ix_findings_status ON findings (status);
CREATE INDEX ix_findings_platform ON findings (platform);
CREATE INDEX ix_findings_score ON findings (score);
