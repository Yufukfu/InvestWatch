-- THROWAWAY test schema. The scraper never creates tables (ADR 0303); module C's Alembic migration is
-- the source of truth. Until it lands this mirrors openspec/changes/scraper-ingest/migration-request.md.
-- The base columns of sources/documents are an ASSUMPTION (integration-plan §3: "simple columns + payload JSONB").
CREATE TABLE sources (
  id uuid PRIMARY KEY,
  name text NOT NULL,
  platform text NOT NULL,
  url text NOT NULL,
  source_kind text NOT NULL,
  active boolean NOT NULL DEFAULT true,
  last_run_at timestamptz NULL
);

CREATE TABLE documents (
  id uuid PRIMARY KEY,
  source_id uuid NULL REFERENCES sources (id),
  platform text NOT NULL,
  source_kind text NOT NULL,
  url text NOT NULL,
  fetched_at timestamptz NOT NULL,
  content_hash text NULL,
  html_object_key text NULL,
  payload jsonb NOT NULL
);

CREATE UNIQUE INDEX documents_source_content_hash_uq
  ON documents (source_id, content_hash)
  WHERE source_id IS NOT NULL AND content_hash IS NOT NULL;

ALTER TABLE documents ADD COLUMN committed_at timestamptz NOT NULL DEFAULT now();
ALTER TABLE documents ADD COLUMN stream_published_at timestamptz NULL;
CREATE INDEX documents_unpublished_idx ON documents (committed_at)
  WHERE stream_published_at IS NULL;

ALTER TABLE sources ADD COLUMN last_run_status text NULL
  CHECK (last_run_status IN ('ok', 'partial', 'failed', 'running'));
ALTER TABLE sources ADD COLUMN documents_count integer NULL CHECK (documents_count >= 0);

CREATE TABLE job_errors (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id uuid NULL,
  reason text NOT NULL CHECK (reason IN (
    'blocked', 'blocked_target', 'timeout', 'http_error', 'parse_error', 'empty_text',
    'schema_invalid', 'storage_error', 'publish_failed', 'invalid_request')),
  detail text NULL,
  at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX job_errors_source_at_idx ON job_errors (source_id, at DESC);
