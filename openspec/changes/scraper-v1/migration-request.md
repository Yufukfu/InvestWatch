# Migration request for module C (`api/` Alembic, ADR 0303)

The scraper does not create or alter tables (ADR 0303). It needs the additions below on top of the `sources` and `documents` tables from `.docs/integration-plan.md` §3. Plain SQL for you to translate to Alembic; names are proposals. It assumes `documents.source_id` and `documents.content_hash` are real columns (integration plan §3 says "simple columns + payload JSONB"), and `documents.id` uuid.

```sql
-- documents: dedup by (source, content_hash). Partial, because the contract allows
-- source_id and content_hash to be null (ad-hoc documents); the scraper always sets both.
-- The scraper's INSERT uses: ON CONFLICT (source_id, content_hash)
--   WHERE source_id IS NOT NULL AND content_hash IS NOT NULL DO NOTHING
CREATE UNIQUE INDEX documents_source_content_hash_uq
  ON documents (source_id, content_hash)
  WHERE source_id IS NOT NULL AND content_hash IS NOT NULL;

-- documents: publish marker for the republish sweep
-- (named so it cannot be confused with the article's published_at)
ALTER TABLE documents ADD COLUMN committed_at timestamptz NOT NULL DEFAULT now();
ALTER TABLE documents ADD COLUMN stream_published_at timestamptz NULL;  -- NULL = not yet on iw:documents
CREATE INDEX documents_unpublished_idx ON documents (committed_at)
  WHERE stream_published_at IS NULL;

-- sources: written by the scraper when a job starts ('running') and at its final outcome (source.schema.json)
-- documents_count = new documents of the LAST job, not a running total (confirm with B that the dashboard reads it so)
-- last_run_at already exists per integration-plan §3
ALTER TABLE sources ADD COLUMN last_run_status text NULL
  CHECK (last_run_status IN ('ok', 'partial', 'failed', 'running'));
ALTER TABLE sources ADD COLUMN documents_count integer NULL CHECK (documents_count >= 0);

-- job errors: source_id is deliberately NOT a foreign key (a scan request can name a source that does not exist)
CREATE TABLE job_errors (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id uuid NULL,
  reason text NOT NULL CHECK (reason IN (
    'blocked', 'blocked_target', 'timeout', 'http_error', 'parse_error', 'empty_text',
    'schema_invalid', 'storage_error', 'publish_failed', 'invalid_request')),
  detail text NULL,           -- never holds credentials
  at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX job_errors_source_at_idx ON job_errors (source_id, at DESC);
```

Also needed from C for `scraper-v1`: a `docker-compose.yml` (or the shared compose file) with `postgres`, `redis` and `minio`, and the `iw-raw` bucket is created by the scraper itself at startup.

Plan note: `.docs/integration-plan.md` §6 (scan `status`) and §3 (`sources.last_run_status`, `documents_count`) are stale against `contracts/schemas/events.schema.json` and `source.schema.json`.
