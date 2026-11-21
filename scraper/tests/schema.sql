-- THROWAWAY test schema. The scraper never creates tables (ADR 0303); module C's Alembic revision
-- (branch api/api-v1, api/migrations/versions/0001_initial.py) is the source of truth. This mirrors the
-- columns and constraints the scraper touches. Ids have no server default: the producer generates UUID v4.
CREATE TABLE sources (
  id uuid PRIMARY KEY,
  name text NOT NULL,
  platform text NOT NULL,
  url text NOT NULL,
  source_kind text NOT NULL,
  active boolean NOT NULL DEFAULT true,
  last_run_at timestamptz NULL,
  last_run_status text NULL CHECK (last_run_status IN ('ok', 'partial', 'failed', 'running'))
);

CREATE TABLE documents (
  id uuid PRIMARY KEY,
  source_id uuid NULL REFERENCES sources (id),
  platform text NOT NULL,
  source_kind text NOT NULL,
  url text NOT NULL,
  canonical_url text NULL,
  fetched_at timestamptz NOT NULL,
  published_at timestamptz NULL,
  http_status integer NULL CHECK (http_status BETWEEN 100 AND 599),
  lang text NULL CHECK (lang ~ '^[a-z]{2}$'),
  title text NULL,
  text text NOT NULL,
  content_hash text NULL CHECK (content_hash ~ '^[a-f0-9]{64}$'),
  html_object_key text NULL,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(payload) = 'object'),
  stream_published_at timestamptz NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- one row per (source, text); ad-hoc documents (null source) dedup too; rows without a hash never collide
CREATE UNIQUE INDEX uq_documents_source_hash ON documents (source_id, content_hash)
  NULLS NOT DISTINCT WHERE content_hash IS NOT NULL;
CREATE INDEX ix_documents_unpublished ON documents (created_at) WHERE stream_published_at IS NULL;

CREATE TABLE job_errors (
  id uuid PRIMARY KEY,
  source_id uuid NULL,  -- no foreign key on purpose: errors about unknown sources are kept
  url text NULL,
  reason text NOT NULL CHECK (reason <> ''),
  detail text NULL,
  occurred_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_job_errors_source_occurred ON job_errors (source_id, occurred_at DESC);
