# scraper

Data collection service: collectors for web pages and social media, job queue, scheduler.

- **Owner:** Adam
- **Status:** web collection (`scraper-v1`: fetch, parse, politeness, guards) is implemented as a library; storage and announcement (`scraper-ingest`: validate, dedup, MinIO, `iw:documents`, republish sweep, `job_errors`) is implemented; the queue, scheduler, scan requests, events and the run that joins all pieces (`scraper-orchestration`) are implemented. The first social platform, Telegram public channels (`scraper-v2-social`, ADR 0103), is implemented: a source URL is `https://t.me/s/<handle>`, one document per text post, seed rows in `seeds/telegram.toml`. Facebook, Instagram and TikTok (named in the brief) are not covered.

## Run

`python -m iw_scraper worker` runs the job worker, the scan-request consumer (Redis Stream `iw:scan-requests`) and `GET /health` (port `SCRAPER_HEALTH_PORT`, default 8080, not published by compose). `python -m iw_scraper scheduler` enqueues due sources and runs the republish sweep; run exactly one per stack (a second only wastes ticks, jobs are de-duplicated by slot). Both stop gracefully on SIGTERM: running jobs finish for `SCRAPER_SHUTDOWN_DEADLINE`, the rest is requeued. `python -m iw_scraper.seed [CRON]` registers the KNF source (optional 5-field `CRON`) and every source of the `scraper/seeds/*.toml` files, one `[[source]]` table per page (`name`, `url`, `source_kind`, `target_modules`, optional `schedule_cron` and `platform`, default `web`). It validates all files before writing anything, leaves a source whose URL is already registered untouched (dashboard edits survive) and is safe to run twice or at once. To add a source, add a table to a seed file and run it again. `pytest -m scraper_live tests/test_seed_live.py` re-checks that every seeded URL is final and fetchable; it makes real requests, so run it deliberately. Needs `DATABASE_URL`, `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY` (`MINIO_BUCKET`, `MINIO_SECURE` optional) besides `REDIS_URL`; the stack's `api-migrate` must have run first.

The queue's own Redis keys are prefixed `iw:scraper:` (queue `iw:scraper:queue`; jobs and results are JSON); only `arq`'s `arq:job:` and `arq:result:` keys are fixed by the library. A scheduler that starts late enqueues the slots of the last five minutes it missed.

## Run the tests

Python 3.12 and the native TLS library are only in the image. From the repository root, one command starts the same Redis, PostgreSQL and MinIO images as the stack and runs every test, including the ingest and queue tests:

```bash
COMPOSE_PROJECT_NAME=iw-scraper-orch docker compose -f scraper/compose.test.yaml run --rm --build test
```

Without those services (a bare `docker run` of the image) the service-backed tests are skipped, and with `CI` set they fail.

Opt-in live smoke tests make real requests and are deselected by default (`-m scraper_live`); the Telegram one collects the public channel named in `IW_LIVE_TELEGRAM_HANDLE` once.

## Author provenance

Analytics routes a post to M2 (published by the firm itself) from `author.handle`, `author.profile_url` and the host of `url` (`advertiser.publisher_firm`; `url` is the guarded fetch URL, so a collector must never take it from markup), so where they come from decides whether an impersonator can fake a firm post (issue 36). Read from the code on `main`:

| Platform | `author.handle` | `author.profile_url` | Source | Platform-verified |
|---|---|---|---|---|
| `web` (every source today) | never set | never set | `parsing.parse_page` returns title, text, canonical URL and links only; `document.build_document` emits no `author` | n/a, the field is absent |
| any parsed page that carries an `author` | dropped | dropped | `ingest.document.build_document` ignores `author` on the page: markup (`<meta>`, `rel=author`, embedded JSON) is written by the post's author | no, so it is never stored |
| Telegram (`social/telegram.py`) | channel handle | `https://t.me/<handle>` built from the handle | `social/telegram.py` takes the handle from the source URL `t.me/s/<handle>` (never from page text) and ignores posts of another channel; `social/model.build_author` builds the `author`, and `collect.py` passes it to `Ingestor.ingest` as the `author=` argument (the page dict from `build_page` never carries one) | the handle is the source row's own channel username; the page only supplies title and followers |

Rule: `author` is set only by a platform collector from the platform's own account data, passed as the `author=` argument of `Ingestor.ingest` / `build_document`, never copied from the page dict. A document without `author` is a valid `ScrapedDocument`; consumers must treat it as "unknown", not "third party". `ingest.validate` only checks that `profile_url` is an http(s) URL, not who wrote it. A positive "verified" flag would need a `scrape_meta` field, which is a contract change (proposal: an optional `scrape_meta.author_source`, `platform_account | page_markup | unknown`, in the [issue 36 reply](https://github.com/Yufukfu/InvestWatch/issues/36#issuecomment-7068727126)). When that flag lands, `ingest.document._scrape_meta` must drop it from a page-supplied `scrape_meta` and set it only when `author=` is given, because today it keeps every page key and a parser could otherwise claim `platform_account`.

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
| `SOCIAL_MAX_POSTS` | `40` | posts of a social channel read per run, rounded up to whole pages of twenty (a Telegram source URL is `https://t.me/s/<handle>`) |
| `ALLOWED_PORTS` | `80,443` | ports the scraper may request |
| `COMPOSE_INTERNAL_HOSTS` | empty | extra host names refused as internal (bare names are always refused) |
| `FETCH_EXTRA_HOSTS` | empty | hosts allowed for redirects and scraped links besides the active sources |
| `CONTRACTS_DIR` | `<repo>/contracts` | JSON Schemas used for validation |
