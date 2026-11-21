# Design

## Context

Stateless Python async code that turns a parsed page into a stored, announced document (`.docs/integration-plan.md` §2-3). It knows nothing about analytics and nothing about how the page was fetched. Scope: `proposal.md`.

## Goals / Non-Goals

**Goals:** a failure at any stage leaves no half-written state (no orphan object, no event without a row); at-least-once delivery that analytics can deduplicate.

**Non-Goals:** fetching, parsing, queueing, scheduling.

## Decisions

- **Ingest order: validate, cheap dedup check, upload HTML, insert row, commit, then `XADD`.** A failure before commit publishes nothing; a failure after commit records `publish_failed`, leaves the row unpublished and the sweep republishes it (at-least-once; analytics deduplicates by `document_id`).
- **Dedup in two steps.** A lookup on `(source_id, content_hash)` before the upload, and a unique index with `INSERT ... ON CONFLICT DO NOTHING` for the race. Any failure after the upload (conflict or other error) removes the object. `source_id` is always set, because NULLs would defeat the index. The scraper creates `iw-raw` at startup if absent.
- **Hash normalisation keeps case.** NFC, whitespace collapsed and trimmed, no case folding: capitalisation can carry meaning in risk wording. Volatile page text still produces new rows; stripping it is per-site parser work.
- **Republish sweep** claims rows that are unpublished and older than a grace period with `FOR UPDATE SKIP LOCKED`. The row lock separates concurrent sweeps; only the grace period protects a run that is still publishing. A crash between `XADD` and the marker update can publish twice, which analytics tolerates.
- **Schema changes are not created by this service.** The migration items in `proposal.md` are Alembic migrations under `api` (integration plan §7). `api/` does not exist yet, so task 1.4 agrees with C who writes them; groups needing the database wait for it.
- **Job errors** go to a `job_errors` table (source_id nullable, no foreign key, reason, detail, at) plus a JSON log line. Detail never holds credentials.
- **Contracts in the image**: `CONTRACTS_DIR` points at `contracts/` (the image build context includes it, see `scraper-v1`).

## Risks / Trade-offs

- [Volatile page text creates new rows] -> stripping it is per-site parser work in `scraper-v1`, not hash work.
- [Redis publish lost after commit] -> republish sweep.
- [Migration late] -> tests run on a throwaway schema; the real migration is checked in `scraper-orchestration`'s end-to-end test.

## Open Questions

- None blocking. The published marker is `documents.stream_published_at` with `committed_at` (`migration-request.md`); C may rename them without changing the specs.
