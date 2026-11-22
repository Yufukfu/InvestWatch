# scraper

Owners: [`.github/CODEOWNERS`](../.github/CODEOWNERS).

Collects web and social-media content and writes `ScrapedDocument` rows (contract v1, `.docs/integration-plan.md` §3) plus HTML and screenshots to MinIO. Downstream, `analytics` consumes the Redis Stream `iw:documents`; the scraper knows nothing about analytics.

Run `iw-scraper-conventions` before writing any fetch or parse code. Team decision: start with **one** social platform, add more only if time allows. Behaviour lives in `openspec/specs/web-collection/` (and the in-flight changes in `openspec/changes/`); config and run steps in [`README.md`](README.md).

## Stack

- Python 3.12 only (the local Python is older: run everything in the image). Async-first.
- Fetch: `noble-tls` (ADR 0101) with the `CHROME_146_PSK` profile; the Dockerfile pins the native `tls-client` library by tag and sha256. Parse: `lxml`. Shared state: `redis` (rate limit, `Retry-After`, failure pause). `robots.txt`: `protego`. Playwright lives only in the separate `renderer` service (ADR 0107), for sources that need `blocks`/`screenshots`.
- Job queue and schedule: `arq` (ADR 0102), in `scraper-orchestration`. Storage: PostgreSQL + MinIO + Redis from the shared stack, in `scraper-ingest`. Deployment: `scraper/compose.yaml` (`worker`, `scheduler`, one-shot `seed`; ADR 0106), checked by `scraper/tests/stack.sh`; the root `compose.yaml` includes it.
- Modules in `src/iw_scraper/`: `fetch` (one attempt, manual redirects, IP pinning), `identities` (UA, client hints and TLS profile as one unit), `proxy` (rotation, cooldown), `robots`, `ratelimit`, `domaingate` (`Retry-After`, failure pause), `targets` (selection, URL, port and address guards), `document` (the contract fields as a dict), `parsing`, `reporting`, `config`, `types`, `social/` (platform-neutral `model`, the `registry` of collectors by host, one module per platform: `telegram`). Pieces take their guard, clock and Redis client as parameters. Orchestration: `collect` (`run_source`, one attempt), `jobs` (arq wrapper: retry, per-domain cap, run lock, `scan.*` events), `guards`, `retry`, `events`, `scan_requests`, `scheduler`, `worker`, `supervise`, `health`, `logs`, `pgstore`, `app` (the `worker` and `scheduler` processes), `seed` (the KNF row and the `seeds/*.toml` loader: validate all files, then insert where the URL is absent, under an advisory lock; spec `source-seeds`), `report` (read-only `python -m iw_scraper.report`: counts and last statuses from the shared tables, no success rate), `discover` (candidate sources from stored links: inactive, never fetched, [ADR 0108](../.docs/decisions/0108-source-discovery-candidates.md); a candidate is activated only by a human), `sample_import` (own entry point: saved HTML or text through the same `Ingestor`; its own wiring, no `app.py`; `author` only from the manifest; usage in [`README.md`](README.md)). `rendering` (the render client, hourly budget and pause check; see Rendering below). The queue owns cross-job domain state (ADR 0102): do not wire `DomainGate` into a collector (only the render step's `DomainPause` reads it, next to the queue's `DomainHealth`).

## Adding a social platform

A module under `src/iw_scraper/social/` with `parse(body, final_url) -> Channel` (and a `valid_url` for the source URL form), one `registry.register(host, parse, platform=..., valid_url=...)`, saved real pages in `tests/fixtures/`, an opt-in `scraper_live` smoke test and a `sources` row (`seeds/*.toml`). `run_source`, ingest and the contract do not change. Check the platform first: robots-allowed, anonymous, our fetch layer (ADR 0103 has the evidence for X, Facebook, Instagram, TikTok and YouTube, which are not covered). A new `platform` value is a contract change for the whole team.

## Tests

pytest, saved real responses in `tests/fixtures/`, no live network in unit tests. The fetch tests need the native TLS library and the Redis tests need a Redis, so run them in the image (`README.md`, "Run the tests"). A failing `REDIS_URL` check is deliberate: those tests do not skip.

## Rules worth repeating

- A session is one attempt: fresh cookies, an identity drawn per run, a proxy picked per request. A block ends the run and is never retried; a `robots.txt` refusal is not a block.
- Every URL (source URL, redirect hop, scraped link) goes through the guards before a request: http(s), allow-listed host, `ALLOWED_PORTS`, then our own DNS and a public address; connect to the address that was checked.
- `author` is never taken from claims a page's writer controls (`<meta>`, `rel=author`, embedded JSON; `ingest.document.build_document` drops it): analytics routes on `author.handle` / `profile_url` (and the host of `url`), so only a platform collector may set it, from the platform's own account fields, via the `author=` argument. Provenance per platform: [`README.md`](README.md), "Author provenance".
- Errors use the closed `Reason` set; details never carry a proxy URL, credentials, a path or a query.

## Rendering (`src/iw_renderer/`, `src/iw_scraper/rendering.py`)

Only `firm_own` sources that target `M2` are rendered, and only with `SCRAPER_RENDER_ENABLED=true`. `Collector` attaches `document["render"]` (an async callable); `Ingestor` runs it after the duplicate check and before the first upload, stores `shot/{id}/{viewport}.png`, sets `screenshots`, `blocks` and `scrape_meta.render`, and on a failure stores the document without them plus a job error (a failed viewport other than a block or a refused target keeps the ones already taken, `null` for the rest; `blocked`, `blocked_target`, `storage_error`, `render_failed`). The renderer container is hostile-page territory: no secrets, `egress` and an internal `render` network only, every browser request confined (`confine.py`); do not add a credential, a port or a network to it. Behaviour in `openspec/specs/page-rendering/` once archived, reasoning in [ADR 0107](../.docs/decisions/0107-playwright-renderer-service.md). Renderer tests run in the `renderer-test` image (`README.md`).

## Ingest (`src/iw_scraper/ingest/`)

`Ingestor.ingest` is the one entry point: validate, dedup pre-check, upload HTML, insert, then `XADD`; `sweep` republishes rows whose announcement was lost. Spec `scraper-ingest` (capability `document-ingest`), reasoning in [ADR 0104](../.docs/decisions/0104-ingest-order-and-republish-sweep.md). Rules that bite: `content_hash` is defined once (NFC, whitespace collapsed, case kept; [ADR 0105](../.docs/decisions/0105-content-hash-normalisation.md), `.docs/integration-plan.md` §3) and `tests/test_ingest_document.py` pins it with literal hashes, so never switch it to NFKC; the schema belongs to `api/` (Alembic; never create or alter a table here); `iw-raw` is created by `minio-init`, the service only checks it (`Storage.check_bucket`); the conflict target of the insert is named and must match the partial unique index of the `api/` migration `0001`; `job_errors.detail` is redacted but must still never be given credentials. Nothing calls these yet: the wiring (sink adapter, `page` dict with `html`, `check_bucket` at startup, the scheduled sweep) is still to be assigned between `scraper-v1` and `scraper-orchestration`. Tests need PostgreSQL, Redis and MinIO (`IW_TEST_*`, see [`README.md`](README.md)); a mutation check goes on every guard (`iw-commit-cycle`).

Re-scans: `Ingestor.rescan_state` and `record_gone` report an edited page (`previous_document_id`, a `rescan_outcome` log line) and a removed one (`http_error` `HTTP 404`/`HTTP 410` with the source URL, which the api reads; no failed run); the web flow in `collect.py` confirms a 404/410 once. State is derived from `documents` and `job_errors`, never a new column ([ADR 0110](../.docs/decisions/0110-rescan-changed-and-removed-derivation.md), [`README.md`](README.md), "Re-scan outcomes").

## Done means

Schema-valid documents land in `documents`, an `XADD iw:documents` follows, a rerun dedups by `content_hash`, and a block or parse failure is logged as a job error instead of an empty document.
