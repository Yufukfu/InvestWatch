# Design

## Context

Module A is a stateless Python async service that scales by replica count. It reads `sources` from PostgreSQL, writes `documents` and raw HTML (MinIO `iw-raw`), and announces new rows on Redis Stream `iw:documents` (`.docs/integration-plan.md` §2-3). It knows nothing about analytics. Fetch-layer rules: `iw-scraper-conventions`. Scope: `proposal.md`.

## Goals / Non-Goals

**Goals:**
- One pipeline `source -> job -> fetch -> parse -> validate -> store -> publish`, each stage a small unit testable without network.
- Failures are first-class: every non-success outcome is a typed job error.
- Horizontal scale and stability without coordination code: shared state only in Redis or PostgreSQL.
- A site is added by a parser module and a `sources` row.

**Non-Goals:**
- Social collectors, Playwright rendering (`blocks`, screenshots), crawling beyond one URL per run, proxy pool health management.

## Decisions

- **One URL per run in v1.** A run fetches the source URL, follows redirects hop by hop and reads `robots.txt`. Scenarios about "every fetch of a run" mean that one fetch.
- **Terms.** Job = one enqueued unit for a source; attempt = one execution of it by the queue (retries make several); run = the fetching of one attempt; session = the state of one run. The run lock and `scan.*` events belong to the job; sessions and identities belong to the attempt; the domain failure count is per job final outcome.
- **Session = one run (one attempt).** Empty cookie jar, a newly drawn identity (user agent, ordered header set, TLS profile of one browser family), nothing reused across attempts, runs or sources. The proxy is not part of the identity: it is chosen per request (`PROXY_ROTATION=per_request`, default; random start, never the same proxy twice in a row; a 407 puts that proxy on `PROXY_COOLDOWN_SECONDS`, default 90; when every proxy is cooling the attempt is deferred, not failed). Trade-off: a site that binds a session cookie to an IP can break under per-request rotation, hence the `per_session` switch.
- **Header order is data, not code.** The identity table lists headers lowercase in the browser's wire order, one entry per browser version, driving the user agent, `sec-ch-ua` and the TLS profile together. The order is verified on the wire with a raw-socket stub; browser DevTools show headers alphabetised and must not be used as the reference. A run blocked on every proxy is investigated as a header problem first.
- **Fetch client** behind `fetch(url, identity, proxy)`; one attempt, manual redirect hops, streaming size cap. The client choice is ADR 0101; whether it can pin the resolved IP and take explicit header order is settled by an early spike (task 3.1) before `fetch()` is built.
- **Queue and scheduler**: `arq` on Redis (ADR 0102). The queue is the only place that retries (`timeout` and 5xx, capped, backoff with jitter, `Retry-After` can raise a delay, never shorten it). `schedule_cron` strings are parsed by us. Each due job gets a unique id per source and cron slot, so replicas never double-enqueue.
- **Shared state in Redis**, two separate per-domain controls: a *rate limit* (token bucket in a Lua script, local fallback when Redis is down, as in `hen68/cheaply-self-hosted` `shared/ratelimit.py`) that spaces request starts, and a *concurrency cap* (counting semaphore with expiring leases) on jobs running at once. Also `Retry-After` deferral, a per-domain failure cooldown (consecutive failed jobs) and a per-source run lock held for the whole job and renewed while it lives. Stale leases and locks expire, so a crash cannot make a source unrunnable. A job that meets a deferral, a paused domain or an all-proxies-cooling state is requeued with a delay: not a failure, no retry consumed, no event.
- **Scan requests** go through a consumer group with a stable consumer name per worker and a periodic claim of messages pending too long. The consumer only enqueues; the job does the work, so there is one code path. A refused request with a valid `source_id` publishes `scan.finished` with `status: failed`, so the dashboard progress bar never hangs. `scan.*` fire once per job, not per retry. A requested job that ends without running (source deactivated after enqueue) publishes `scan.finished` failed; a scheduled one stays silent; a coalesced one is silent because the running job covers the source.
- **Ingest order: validate, cheap dedup check, upload HTML, insert row, commit, then `XADD`.** A failure before commit publishes nothing; a failure after commit records `publish_failed`, leaves the row unpublished and the sweep republishes it (at-least-once; analytics deduplicates by `document_id`).
- **Dedup in two steps.** A lookup on `(source_id, content_hash)` before the upload, and a unique index with `INSERT ... ON CONFLICT DO NOTHING` for the race. Any failure after the upload (conflict or other error) removes the object. `source_id` is always set, because NULLs would defeat the index. The scraper creates `iw-raw` at startup if absent.
- **Hash normalisation keeps case.** NFC, whitespace collapsed and trimmed, no case folding: capitalisation can carry meaning in risk wording. Volatile page text still produces new rows; stripping it is per-site parser work.
- **Republish sweep** claims rows that are unpublished and older than a grace period with `FOR UPDATE SKIP LOCKED`. The row lock separates concurrent sweeps; only the grace period protects a run that is still publishing. A crash between `XADD` and the marker update can publish twice, which analytics tolerates.
- **Fetch allow-list = hosts of active `sources` rows plus configured extras** (`www.` equivalent), applied to every redirect hop and every URL from scraped content, never to the source URL itself (it is on the list by construction); the source URL gets scheme and address checks. Then a refusal of private, loopback, link-local, unique-local, unspecified, multicast and IPv4-mapped addresses after our own DNS resolution, connecting to the checked address.
- **SSRF residual risk**: behind a proxy the proxy resolves DNS itself, so a rebinding answer there cannot be excluded; accepted for the hackathon because `PROXY_LIST` is operator-controlled.
- **Schema changes are not created by this service.** The migration items in `proposal.md` are Alembic migrations under `api` (integration plan §7). `api/` does not exist yet, so task 1.4 agrees with C who writes them; groups needing the database wait for it.
- **`scrape_meta.scraper`** has no exact v1 value for a TLS-impersonating client (enum `playwright|httpx|api|manual`); it is not a required field, and task 1.3 settles it with C. This change does not pick a value in a contract file.
- **Job errors** go to a `job_errors` table (source_id nullable, no foreign key, reason, detail, at) plus a JSON log line. Detail never holds credentials.
- **Scheduler and worker process layout**: the integration plan lists a `scheduler` service; here it is the same image run with a different command (`arq` worker vs cron enqueuer), both stateless. The `/health` endpoint runs in each.
- **Contracts in the image**: `CONTRACTS_DIR` points at `contracts/`, which the image build context includes.

## Risks / Trade-offs

- [Client fingerprint blocked by a target] -> the `fetch()` seam allows swapping the client; a site that needs rendering is handled by `scraper-v3`.
- [Parser breaks on layout change] -> fixture tests per site, a live canary test (opt-in, outside CI) and `parse_error`/`empty_text` errors, never empty documents.
- [Per-request proxy rotation breaks cookie-bound sites] -> `PROXY_ROTATION=per_session`.
- [Contract still draft] -> the schema is loaded from `contracts/`, not copied.
- [Redis publish lost after commit] -> republish sweep.
- [Redis down] -> rate limiting falls back to a process-local limiter with a warning; the worker stays up and `/health` reports it.

## Open Questions

- None blocking. The published marker is the `documents.stream_published_at` column with `committed_at` (proposed DDL in `migration-request.md`); C may rename them without changing the specs.
