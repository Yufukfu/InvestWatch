# Design

## Context

Stateless Python async code that turns a parsed page into a stored, announced document (`.docs/integration-plan.md` §2-3). It knows nothing about analytics and nothing about how the page was fetched. Scope: `proposal.md`.

## Goals / Non-Goals

**Goals:** a failure at any stage leaves no half-written state (no orphan object, no event without a row); at-least-once delivery that analytics can deduplicate.

**Non-Goals:** fetching, parsing, queueing, scheduling.

## Decisions

- **Ingest order: validate, cheap dedup check, upload HTML, insert row, commit, then `XADD`.** A failure before commit publishes nothing; a failure after commit records `publish_failed`, leaves the row unpublished and the sweep republishes it (at-least-once; analytics deduplicates by `document_id`).
- **Dedup in two steps.** A lookup on `(source_id, content_hash)` before the upload, and the partial unique index `uq_documents_source_hash` with a named target, `INSERT ... ON CONFLICT (source_id, content_hash) WHERE content_hash IS NOT NULL DO NOTHING`, for the race (a bare `ON CONFLICT DO NOTHING` would also hide a reused `id`). Any failure after the upload (conflict or other error) removes the object. `source_id` is always set because collected documents come from a `sources` row (the index is `NULLS NOT DISTINCT`, so ad-hoc rows dedup too). The scraper only checks at startup that `iw-raw` exists and fails clearly if not: `minio-init` (module C) creates it, and the app user is limited to that bucket.
- **Hash normalisation keeps case.** NFC, whitespace collapsed and trimmed, no case folding: capitalisation can carry meaning in risk wording. Volatile page text still produces new rows; stripping it is per-site parser work.
- **Republish sweep** claims rows that are unpublished and older than a grace period (`documents.created_at`, ordered by `created_at, id`) with `FOR UPDATE SKIP LOCKED`. The row lock separates concurrent sweeps; only the grace period protects a run that is still publishing. A crash between `XADD` and the marker update can publish twice, which analytics tolerates.
- **Schema changes are not created by this service.** Module C writes the Alembic revision `0001_initial` (branch `api/api-v1`; its `api/README.md` holds the SQL the scraper uses). Tests run on a throwaway schema in `scraper/tests/schema.sql` that mirrors it; ids have no server default, so the scraper generates UUID v4 for `documents` and `job_errors`.
- **Job errors** go to a `job_errors` table (`id` generated here, `source_id` nullable with no foreign key, `url`, `reason`, `detail`, `occurred_at`) plus a JSON log line; a blank `text` is recorded as `empty_text` instead of a junk row. Detail never holds credentials.
- **Contracts in the image**: `CONTRACTS_DIR` points at `contracts/` (the image build context includes it, see `scraper-v1`).

## Risks / Trade-offs

- [Volatile page text creates new rows] -> stripping it is per-site parser work in `scraper-v1`, not hash work.
- [Redis publish lost after commit] -> republish sweep.
- [`job_errors.url` is never written] -> `JobError` (shared types, `scraper-v1`) has no `url` field, so the page URL is not in the sink; add the field in a follow-up change if the dashboard needs it.
- [Orphan objects after a crash] -> cancellation and every failure after the upload remove the object, but a hard crash between upload and insert still leaves one; a periodic list-and-diff of `iw-raw` against `documents.html_object_key` is a possible follow-up.
- [`check_bucket` is not wired] -> the startup call belongs to the service entry point in `scraper-orchestration`.
- [Schema drift] -> the throwaway test schema mirrors module C's `0001_initial`; the real migration is exercised in `scraper-orchestration`'s end-to-end test. A new column needs a new revision from C, never an edit of an applied one.

## Open Questions

- None blocking. The published marker is `documents.stream_published_at` and the sweep age is `documents.created_at`, as agreed with C (no `committed_at` column).
