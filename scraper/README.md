# scraper

Data collection service: collectors for web pages and social media, job queue, scheduler.

- **Owner:** Adam
- **Status:** web collection (`scraper-v1`: fetch, parse, politeness, guards) is implemented as a library; storage and announcement (`scraper-ingest`: validate, dedup, MinIO, `iw:documents`, republish sweep, `job_errors`) is implemented; the queue, scheduler, scan requests, events and the run that joins all pieces (`scraper-orchestration`) are implemented. The first social platform is `scraper-v2`.

## Run

`python -m iw_scraper worker` runs the job worker, the scan-request consumer (Redis Stream `iw:scan-requests`) and `GET /health` (port `SCRAPER_HEALTH_PORT`, default 8080, not published by compose). `python -m iw_scraper scheduler` enqueues due sources and runs the republish sweep; run exactly one per stack (a second only wastes ticks, jobs are de-duplicated by slot). Both stop gracefully on SIGTERM: running jobs finish for `SCRAPER_SHUTDOWN_DEADLINE`, the rest is requeued. `python -m iw_scraper.seed [CRON]` registers the KNF source (optional 5-field `CRON`) and every source of the `scraper/seeds/*.toml` files, one `[[source]]` table per page (`name`, `url`, `source_kind`, `target_modules`, optional `schedule_cron` and `platform`, default `web`). It validates all files before writing anything, leaves a source whose URL is already registered untouched (dashboard edits survive) and is safe to run twice or at once. To add a source, add a table to a seed file and run it again. `pytest -m scraper_live tests/test_seed_live.py` re-checks that every seeded URL is final and fetchable; it makes real requests, so run it deliberately. The worker and the scheduler need `DATABASE_URL`, `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY` (`MINIO_BUCKET`, `MINIO_SECURE` optional) besides `REDIS_URL`; the stack's `api-migrate` must have run first.

The queue's own Redis keys are prefixed `iw:scraper:` (queue `iw:scraper:queue`; jobs and results are JSON); only `arq`'s `arq:job:` and `arq:result:` keys are fixed by the library. A scheduler that starts late enqueues the slots of the last five minutes it missed.

`python -m iw_scraper.discover [--since HOURS] [--limit N] [--dry-run]` reads the links of documents already stored and inserts new hosts as inactive `[candidate] <host>` sources (no network call, [ADR 0108](../.docs/decisions/0108-source-discovery-candidates.md)); approve one with `PATCH /api/sources/{id}` (set `active`, a real `name`, `source_kind`, `schedule_cron`), and run one discovery at a time. Needs only `DATABASE_URL`.

## Run in the stack

`docker compose up --build` at the repository root starts `worker`, `scheduler` and a one-shot `seed` (`scraper/compose.yaml`) after `api-migrate` and `minio-init`; there is nothing to start by hand. `seed` registers the KNF source with the cron `SCRAPER_SEED_CRON` (default `0 */6 * * *`, UTC; an invalid value stops the stack at `seed`), so the scheduler scans it on schedule; a scan can also be requested from the dashboard. Scale collectors with `docker compose up --scale worker=3`, keep one `scheduler`. Operator settings (`PROXY_LIST`, `SCRAPER_SEED_CRON`, `FETCH_*`, ...) are in the root `.env.example`. `worker` needs internet access (`egress`); `worker` serves `/health` on `SCRAPER_HEALTH_PORT` to the stack's networks only, and no scraper container publishes a host port.

Hardware: the containers are limited to 1 CPU / 768 MB (`worker`), 0.5 CPU / 256 MB (`scheduler`) and 0.5 CPU / 128 MB (`seed`, exits after seconds), about 2 CPUs and 1.2 GB together at most. These limits are first estimates, not measured on the demo machine. Check the deployment with `scraper/tests/stack.sh` (needs Docker and network; `config`, `root` and `run` groups; `STACK_ROOT=1` runs it through the root `compose.yaml`).

## Import saved samples

`python -m iw_scraper.sample_import DIR` loads saved files (`.html`, `.htm`, `.txt`, `.md`) through the normal ingest: validation, dedup by `content_hash`, raw HTML to MinIO, a `documents` row, `XADD iw:documents`. It makes no network request except to PostgreSQL, Redis and MinIO and needs the same environment as the worker. Run it in the scraper image with the directory mounted read-only (`docker run --rm -v "$PWD/samples:/samples:ro" --env-file .env iw-scraper python -m iw_scraper.sample_import /samples/uknf --kind third_party --modules M3`, on the stack's network); a rerun inserts nothing and reports duplicates.

- **Routing is never inferred.** Without a `samples.toml` in `DIR`, `--kind` (`firm_own`, `third_party`, `unknown`) and `--modules` (`M1,M2,M3`) are required. With one, the manifest wins over the flags. Every value is checked against the contract before anything is read or stored.
- **`samples.toml`:** set-level keys `name`, `url` (the set's source), `source_kind`, `platform` (default `web`), `target_modules`, `lang`, `published_at`, `author`; per-file overrides in `[files."name.html"]` for `url` (the page it was saved from, shown in the dashboard), `source_kind`, `platform`, `target_modules`, `title`, `lang`, `published_at`, `author`. An `.html` file that is valid UTF-8 is parsed as UTF-8 like a fetched page; any other file is decoded by its `<meta charset>`. A file entry for a file that is not in `DIR` is refused. `published_at` is an RFC 3339 date-time with an offset. Without a per-file `url`, a document gets `https://sample.invalid/{set}/{file}` (the stored schema accepts only http(s); `.invalid` never resolves), so the dashboard link is dead.
- **One inactive source per set** (`active = false`, no cron, matched by URL, never updated), so the scheduler and collector never select it. Documents of one set share its `source_id`; dedup is per set.
- **`author` comes only from the manifest**, supplied by the operator and not verified by a platform; take it from the account, not the page (see "Author provenance"). `<meta name="author">` is ignored.
- Reads regular files directly inside `DIR` only: no recursion, no symlink, nothing larger than `FETCH_MAX_BYTES`; `samples.toml` and dotfiles are not samples. PDF and DOCX are skipped (add a reader to `READERS`); `.txt` is the fallback.
- **Report:** one JSON log line per file (`file`, `outcome`, `document_id` when inserted, so a gold label can be attached) and one `sample_summary` line (`inserted`, `duplicate`, `skipped`, `failed`); nothing is printed. A failed file is a `job_errors` row and does not stop the others. Exit code 0, 1 when any file failed, 2 on a usage or manifest error.
- Imported HTML has no `blocks` or screenshots, so the visual M2 rules stay `not_applicable`.

## Run the tests

Python 3.12 and the native TLS library are only in the image. From the repository root, one command starts the same Redis, PostgreSQL and MinIO images as the stack and runs every test, including the ingest and queue tests:

```bash
COMPOSE_PROJECT_NAME=iw-scraper-orch docker compose -f scraper/compose.test.yaml run --rm --build test
```

Without those services (a bare `docker run` of the image) the service-backed tests are skipped, and with `CI` set they fail.

## Effectiveness report

`python -m iw_scraper.report [--since HOURS] [--json]` (needs `DATABASE_URL`; run it in the scraper image) prints what the scraper collected and what failed from `sources`, `documents` and `job_errors`: per active source the last run status, documents (total, in the window, latest `fetched_at`) and job errors of the window by reason; then the never-run and no-document sources, inactive sources apart, and totals (documents by platform and kind, share with raw HTML, errors by reason). `--since` is a whole number of hours from 1 to 87600, ten years (default 24); `--json` prints one JSON object. It reads all three tables in one read-only, repeatable-read transaction (one snapshot), shows sources by id and name (no URL) and never `job_errors.detail`; the report goes to stdout, log lines to stderr, and a database failure exits non-zero.

It cannot give a success rate: the schema keeps only the last run of each source, so statuses are of the last run and nothing older, and the header says so.

## Author provenance

Analytics routes a post to M2 (published by the firm itself) from `author.handle`, `author.profile_url` and the host of `url` (`advertiser.publisher_firm`; `url` is the guarded fetch URL, so a collector must never take it from markup), so where they come from decides whether an impersonator can fake a firm post (issue 36). Read from the code on `main`:

| Platform | `author.handle` | `author.profile_url` | Source | Platform-verified |
|---|---|---|---|---|
| `web` (every source today) | never set | never set | `parsing.parse_page` returns title, text, canonical URL and links only; `document.build_document` emits no `author` | n/a, the field is absent |
| sample import (`sample_import`, from `samples.toml`) | the manifest's `handle` | the manifest's `profile_url` | passed as the `author=` argument, never through the page dict; markup is ignored | no: operator-supplied |
| any parsed page that carries an `author` | dropped | dropped | `ingest.document.build_document` ignores `author` on the page: markup (`<meta>`, `rel=author`, embedded JSON) is written by the post's author | no, so it is never stored |
| Telegram (`scraper/scraper-v2-social`, not on `main`) | channel handle | `https://t.me/<handle>` built from the handle | `social/telegram.py` parses the handle from the `t.me/s/<handle>` preview header; `social/model.build_page` puts it in the page dict's `author`, which the ingest now drops until it is passed through the `author=` argument | the handle is the channel's unique platform username, but it is parsed from preview HTML, not an API; not verified beyond that |

Rule: `author` is set only by a platform collector from the platform's own account data, passed as the `author=` argument of `Ingestor.ingest` / `build_document`, never copied from the page dict. `scraper-v2-social` must switch `build_page` from `page["author"]` to that argument when it rebases, or its posts will have no author. A document without `author` is a valid `ScrapedDocument`; consumers must treat it as "unknown", not "third party". `ingest.validate` only checks that `profile_url` is an http(s) URL, not who wrote it. A positive "verified" flag would need a `scrape_meta` field, which is a contract change (proposal: an optional `scrape_meta.author_source`, `platform_account | page_markup | unknown`, in the [issue 36 reply](https://github.com/Yufukfu/InvestWatch/issues/36#issuecomment-7068727126)). When that flag lands, `ingest.document._scrape_meta` must drop it from a page-supplied `scrape_meta` and set it only when `author=` is given, because today it keeps every page key and a parser could otherwise claim `platform_account`.

## Configuration

Environment only; defaults in `scraper/.env.example`. `config.py` reads and validates each variable; `app.py` passes the values on. The queue, worker and health settings are `SCRAPER_<FIELD>` variables, listed with their defaults in `.env.example`. Proxy URLs may hold credentials: they are never logged, only a `proxy-xxxxxxxx` identifier is.

| Variable | Default | Meaning |
|---|---|---|
| `PROXY_LIST` | empty (direct) | comma-separated `http`, `https` or `socks5` proxy URLs; use an egress-only proxy: behind a proxy the address guard checks our own DNS answer, but the proxy resolves the host itself |
| `PROXY_ROTATION` | `per_request` | `per_request` or `per_session` |
| `PROXY_COOLDOWN_SECONDS` | `90` | how long a proxy that answered 407 is skipped |
| `REDIS_URL` | `redis://localhost:6379/0` | shared rate limit, deferrals and domain pause |
| `DOMAIN_MIN_INTERVAL_SECONDS` | `5` | minimum gap between request starts per domain, all workers |
| `FETCH_TIMEOUT_SECONDS` | `20` | per-request timeout |
| `FETCH_MAX_BYTES` | `5242880` | response size cap (5 MiB) |
| `ALLOWED_PORTS` | `80,443` | ports the scraper may request |
| `COMPOSE_INTERNAL_HOSTS` | empty | extra host names refused as internal (bare names are always refused) |
| `FETCH_EXTRA_HOSTS` | empty | hosts allowed for redirects and scraped links besides the active sources |
| `CONTRACTS_DIR` | `<repo>/contracts` | JSON Schemas used for validation |
