# scraper

Data collection service: collectors for web pages and social media, job queue, scheduler.

- **Owner:** Adam
- **Status:** web collection (`scraper-v1`: fetch, parse, politeness, guards) is implemented as a library; storage and announcement (`scraper-ingest`: validate, dedup, MinIO, `iw:documents`, republish sweep, `job_errors`) is implemented; the queue, scheduler, scan requests, events and the run that joins all pieces (`scraper-orchestration`) are implemented. The first social platform is `scraper-v2`.

## Run

`python -m iw_scraper worker` runs the job worker, the scan-request consumer (Redis Stream `iw:scan-requests`) and `GET /health` (port `SCRAPER_HEALTH_PORT`, default 8080, not published by compose). `python -m iw_scraper scheduler` enqueues due sources and runs the republish sweep; run exactly one per stack (a second only wastes ticks, jobs are de-duplicated by slot). Both stop gracefully on SIGTERM: running jobs finish for `SCRAPER_SHUTDOWN_DEADLINE`, the rest is requeued. `python -m iw_scraper.seed` registers the KNF source once. Needs `DATABASE_URL`, `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY` (`MINIO_BUCKET`, `MINIO_SECURE` optional) besides `REDIS_URL`; the stack's `api-migrate` must have run first.

## Run the tests

Python 3.12 and the native TLS library are only in the image. From the repository root, one command starts the same Redis, PostgreSQL and MinIO images as the stack and runs every test, including the ingest and queue tests:

```bash
COMPOSE_PROJECT_NAME=iw-scraper-orch docker compose -f scraper/compose.test.yaml run --rm --build test
```

Without those services (a bare `docker run` of the image) the service-backed tests are skipped, and with `CI` set they fail.

## Effectiveness report

`python -m iw_scraper.report [--since HOURS] [--json]` (needs `DATABASE_URL`; run it in the scraper image) prints what the scraper collected and what failed from `sources`, `documents` and `job_errors`: per active source the last run status, documents (total, in the window, latest `fetched_at`) and job errors of the window by reason; then the never-run and no-document sources, inactive sources apart, and totals (documents by platform and kind, share with raw HTML, errors by reason). `--since` is a whole number of hours from 1 to 87600, ten years (default 24); `--json` prints one JSON object. It reads in a read-only transaction, shows sources by id and name (no URL) and never `job_errors.detail`; the report goes to stdout, log lines to stderr, and a database failure exits non-zero.

It cannot give a success rate: the schema keeps only the last run of each source, so statuses are of the last run and nothing older, and the header says so.

## Author provenance

Analytics routes a post to M2 (published by the firm itself) from `author.handle`, `author.profile_url` and the host of `url` (`advertiser.publisher_firm`; `url` is the guarded fetch URL, so a collector must never take it from markup), so where they come from decides whether an impersonator can fake a firm post (issue 36). Read from the code on `main`:

| Platform | `author.handle` | `author.profile_url` | Source | Platform-verified |
|---|---|---|---|---|
| `web` (every source today) | never set | never set | `parsing.parse_page` returns title, text, canonical URL and links only; `document.build_document` emits no `author` | n/a, the field is absent |
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
