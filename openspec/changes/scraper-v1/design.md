# Design

## Context

Module A is a standalone Python async service. It reads `sources` from PostgreSQL, writes `documents` and raw HTML (MinIO `iw-raw`), and announces new rows on Redis Stream `iw:documents` (`.docs/integration-plan.md` §2-3). It knows nothing about analytics. Fetch-layer rules: `iw-scraper-conventions`. See `proposal.md` for scope.

## Goals / Non-Goals

**Goals:**
- One pipeline `source -> fetch -> parse -> validate -> store -> publish`, each stage a small unit testable without network.
- Failures are first-class: every non-success outcome is a typed job error.

**Non-Goals:**
- Social collectors, Playwright rendering (`blocks`, screenshots), proxy pool health management.

## Decisions

- **Stages as plain async functions** with explicit inputs and outputs (a `FetchResult`, a parsed document dict, an `IngestResult`), no framework. Alternative: a plugin/collector class hierarchy; rejected as speculative for one platform.
- **Fetch client behind a thin `fetch(url, identity)` function** returning status, headers, body, so the client can be swapped. The client choice (noble-tls vs curl_cffi vs httpx) is hard to reverse and is an ADR draft; its API is read from the installed package before any wrapper is written.
- **Ingest order: validate, cheap dedup check, upload HTML, insert row, commit, then `XADD`.** A failure before commit publishes nothing; a failure after commit records `publish_failed`, marks the row unpublished and leaves it for a republish sweep (delivery is at-least-once; analytics deduplicates by `document_id`). Alternative: outbox table; deferred, the sweep query on unpublished rows is enough for v1.
- **Dedup in two steps.** A lookup on `(source_id, content_hash)` before the upload avoids storing HTML for a known duplicate; a unique index on the same columns with `INSERT ... ON CONFLICT DO NOTHING` closes the race between concurrent workers, and the object is deleted if that insert yields no row. A lookup alone is racy; the index alone orphans an object on every rerun.
- **Fetch allow-list = hosts of active `sources` rows plus configured extras**, checked on the source URL, every redirect hop and every URL from scraped content, followed by a refusal of private, loopback, link-local and compose-internal addresses after DNS resolution. `sources.url` is editable from the dashboard, so it is untrusted too.
- **Schema changes are not created by this service.** The unique index, `job_errors` and the published marker are migrations in Alembic under `api` (integration plan §7). `api/` does not exist yet, so task 1.4 agrees with C who creates them; group 5 waits for it.
- **`scrape_meta.scraper`** has no honest v1 value for a TLS-impersonating client (enum `playwright|httpx|api|manual`). Task 1.3 settles it with C before group 3; this change does not pick a value.
- **Job errors stored in a `job_errors` table** (source_id, reason, detail, at) plus a JSON log line. The scraper writes it and C does not read it, but the table is still created by the shared migration (see above). Detail never holds credentials.
- **Job queue and scheduler**: open-source, chosen by ADR draft (candidates in `.docs/decisions/README.md`). Tasks 1-5 do not depend on it; the scheduling task does.

## Risks / Trade-offs

- [Client fingerprint blocked by a target] -> fetch ladder allows swapping the client or escalating to Playwright for that source only.
- [Parser breaks on layout change] -> fixture tests per source plus `parse_error`/`empty_text` errors, never empty documents.
- [Contract still draft] -> schema file is loaded from `contracts/`, not copied, so a frozen v1 is picked up automatically.
- [Redis publish lost after commit] -> republish sweep over rows without a published marker.

## Open Questions

- Does the published marker live as a `documents` column or a separate table? Deferrable; the sweep query changes, the specs do not.
