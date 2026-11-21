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
- **Ingest order: validate, upload HTML, insert row, commit, then `XADD`.** A failure before commit publishes nothing; a failure after commit records `publish_failed` and leaves the row for a republish sweep. Alternative: outbox table; deferred, the sweep query on unpublished rows is enough for v1.
- **Dedup via a unique index on `(source_id, content_hash)`** with `INSERT ... ON CONFLICT DO NOTHING`, so concurrent workers cannot double-insert. Alternative: select-then-insert; rejected as racy.
- **Job errors stored in a `job_errors` table** (source_id, reason, detail, at) plus a JSON log line. Table ownership is the scraper's; C does not read it.
- **Job queue and scheduler**: open-source, chosen by ADR draft (candidates in `.docs/decisions/README.md`). Tasks 1-5 do not depend on it; the scheduling task does.

## Risks / Trade-offs

- [Client fingerprint blocked by a target] -> fetch ladder allows swapping the client or escalating to Playwright for that source only.
- [Parser breaks on layout change] -> fixture tests per source plus `parse_error`/`empty_text` errors, never empty documents.
- [Contract still draft] -> schema file is loaded from `contracts/`, not copied, so a frozen v1 is picked up automatically.
- [Redis publish lost after commit] -> republish sweep over rows without a published marker.

## Open Questions

- Does the published marker live as a `documents` column or a separate table? Deferrable; the sweep query changes, the specs do not.
