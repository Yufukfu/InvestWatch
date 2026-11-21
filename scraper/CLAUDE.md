# scraper (Adam's module)

Collects web and social-media content and writes `ScrapedDocument` rows (contract v1, `.docs/integration-plan.md` §3) plus HTML and screenshots to MinIO. Downstream, `analytics` consumes the Redis Stream `iw:documents`; the scraper knows nothing about analytics.

Run `iw-scraper-conventions` before writing any fetch or parse code. Team decision: start with **one** social platform, add more only if time allows. Behaviour lives in `openspec/specs/web-collection/` (and the in-flight changes in `openspec/changes/`); config and run steps in [`README.md`](README.md).

## Stack

- Python 3.12 only (the local Python is older: run everything in the image). Async-first.
- Fetch: `noble-tls` (ADR 0101) with the `CHROME_146_PSK` profile; the Dockerfile pins the native `tls-client` library by tag and sha256. Parse: `lxml`. Shared state: `redis` (rate limit, `Retry-After`, failure pause). `robots.txt`: `protego`. Playwright only as a fallback and for sources that need `blocks`/`screenshots` (`scraper-v3`).
- Job queue and schedule: `arq` (ADR 0102), in `scraper-orchestration`. Storage: PostgreSQL + MinIO + Redis from `docker-compose.yml`, in `scraper-ingest`.
- Modules in `src/iw_scraper/`: `fetch` (one attempt, manual redirects, IP pinning), `identities` (UA, client hints and TLS profile as one unit), `proxy` (rotation, cooldown), `robots`, `ratelimit`, `domaingate` (`Retry-After`, failure pause), `targets` (selection, URL, port and address guards), `document` (the contract fields as a dict), `parsing`, `reporting`, `config`, `types`. Pieces take their guard, clock and Redis client as parameters. Orchestration: `collect` (`run_source`, one attempt), `jobs` (arq wrapper: retry, per-domain cap, run lock, `scan.*` events), `guards`, `retry`, `events`, `scan_requests`, `scheduler`, `worker`, `supervise`, `health`, `logs`, `pgstore`, `app` (the `worker` and `scheduler` processes), `seed` (the KNF row and the `seeds/*.toml` loader: validate all files, then insert where the URL is absent, under an advisory lock; spec `source-seeds`), `discover` (candidate sources from stored links: inactive, never fetched, [ADR 0108](../.docs/decisions/0108-source-discovery-candidates.md); a candidate is activated only by a human). The queue owns cross-job domain state (ADR 0102): do not wire `DomainGate` into a collector.

## Tests

pytest, saved real responses in `tests/fixtures/`, no live network in unit tests. The fetch tests need the native TLS library and the Redis tests need a Redis, so run them in the image (`README.md`, "Run the tests"). A failing `REDIS_URL` check is deliberate: those tests do not skip.

## Rules worth repeating

- A session is one attempt: fresh cookies, an identity drawn per run, a proxy picked per request. A block ends the run and is never retried; a `robots.txt` refusal is not a block.
- Every URL (source URL, redirect hop, scraped link) goes through the guards before a request: http(s), allow-listed host, `ALLOWED_PORTS`, then our own DNS and a public address; connect to the address that was checked.
- `author` is never taken from claims a page's writer controls (`<meta>`, `rel=author`, embedded JSON; `ingest.document.build_document` drops it): analytics routes on `author.handle` / `profile_url` (and the host of `url`), so only a platform collector may set it, from the platform's own account fields, via the `author=` argument. Provenance per platform: [`README.md`](README.md), "Author provenance".
- Errors use the closed `Reason` set; details never carry a proxy URL, credentials, a path or a query.

## Ingest (`src/iw_scraper/ingest/`)

`Ingestor.ingest` is the one entry point: validate, dedup pre-check, upload HTML, insert, then `XADD`; `sweep` republishes rows whose announcement was lost. Spec `scraper-ingest` (capability `document-ingest`), reasoning in [ADR 0104](../.docs/decisions/0104-ingest-order-and-republish-sweep.md). Rules that bite: `content_hash` is defined once (NFC, whitespace collapsed, case kept; [ADR 0105](../.docs/decisions/0105-content-hash-normalisation.md), `.docs/integration-plan.md` §3) and `tests/test_ingest_document.py` pins it with literal hashes, so never switch it to NFKC; the schema belongs to Damian's module (Alembic in `api/`, never create or alter a table here); `iw-raw` is created by `minio-init`, the service only checks it (`Storage.check_bucket`); the conflict target of the insert is named and must match Damian's partial unique index; `job_errors.detail` is redacted but must still never be given credentials. Nothing calls these yet: the wiring (sink adapter, `page` dict with `html`, `check_bucket` at startup, the scheduled sweep) is still to be assigned between `scraper-v1` and `scraper-orchestration`. Tests need PostgreSQL, Redis and MinIO (`IW_TEST_*`, see [`README.md`](README.md)); a mutation check goes on every guard (`iw-commit-cycle`).

## Done means

Schema-valid documents land in `documents`, an `XADD iw:documents` follows, a rerun dedups by `content_hash`, and a block or parse failure is logged as a job error instead of an empty document.
