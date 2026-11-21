# scraper

Data collection service: collectors for web pages and social media, job queue, scheduler.

- **Owner:** Adam
- **Status:** web collection (`scraper-v1`: fetch, parse, politeness, guards) is implemented as a library; storage and announcement (`scraper-ingest`: validate, dedup, MinIO, `iw:documents`, republish sweep, `job_errors`) is implemented; queue and schedule follow in `scraper-orchestration`; the first social platform is `scraper-v2`.

## Run the tests

Python 3.12 and the native TLS library are only in the image. From the repository root:

```bash
docker build -f scraper/Dockerfile --target test -t iw-scraper:test .
docker network create iw-scraper-test
docker run -d --name iw-scraper-test-redis --network iw-scraper-test redis:7
docker run --rm --network iw-scraper-test -e REDIS_URL=redis://iw-scraper-test-redis:6379/0 iw-scraper:test
```

The ingest tests also need real PostgreSQL, Redis and MinIO, addressed by `IW_TEST_PG_DSN`, `IW_TEST_REDIS_URL`, `IW_TEST_MINIO_ENDPOINT`, `IW_TEST_MINIO_ACCESS_KEY` and `IW_TEST_MINIO_SECRET_KEY`; without them they are skipped, and with `CI` set they fail. The schema they run on is `tests/schema.sql`, a throwaway copy of Damian's `api/migrations` (0001-0003); the service itself never creates tables or the `iw-raw` bucket.

## Author provenance

Analytics routes a post to M2 (published by the firm itself) from `author.handle` and `author.profile_url`, so where they come from decides whether an impersonator can fake a firm post (issue 36). Read from the code on `main`:

| Platform | `author.handle` | `author.profile_url` | Source | Platform-verified |
|---|---|---|---|---|
| `web` (every source today) | never set | never set | `parsing.parse_page` returns title, text, canonical URL and links only; `document.build_document` emits no `author` | n/a, the field is absent |
| any parsed page that carries an `author` | dropped | dropped | `ingest.document.build_document` ignores `author` on the page: markup (`<meta>`, `rel=author`, embedded JSON) is written by the post's author | no, so it is never stored |
| Telegram (`scraper/scraper-v2-social`, not on `main`) | channel handle | `https://t.me/<handle>` built from the handle | `social/telegram.py` parses the handle from the `t.me/s/<handle>` preview header; `social/model.build_page` puts it in the page dict's `author`, which the ingest now drops until it is passed through the `author=` argument | the handle is the channel's unique platform username, but it is parsed from preview HTML, not an API; not verified beyond that |

Rule: `author` is set only by a platform collector from the platform's own account data, passed as the `author=` argument of `Ingestor.ingest` / `build_document`, never copied from the page dict. `scraper-v2-social` must switch `build_page` from `page["author"]` to that argument when it rebases, or its posts will have no author. A document without `author` is a valid `ScrapedDocument`; consumers must treat it as "unknown", not "third party". `ingest.validate` only checks that `profile_url` is an http(s) URL, not who wrote it. A positive "verified" flag would need a `scrape_meta` field, which is a contract change (proposal in the PR for issue 36).

## Configuration

Environment only; defaults in `scraper/.env.example`. `config.py` reads and validates each variable; the run that joins the pieces (`scraper-orchestration`) passes the values on, so until it exists the library takes them as parameters. Proxy URLs may hold credentials: they are never logged, only a `proxy-xxxxxxxx` identifier is.

| Variable | Default | Meaning |
|---|---|---|
| `PROXY_LIST` | empty (direct) | comma-separated `http`, `https` or `socks5` proxy URLs |
| `PROXY_ROTATION` | `per_request` | `per_request` or `per_session` |
| `PROXY_COOLDOWN_SECONDS` | `90` | how long a proxy that answered 407 is skipped |
| `REDIS_URL` | `redis://localhost:6379/0` | shared rate limit, deferrals and domain pause |
| `DOMAIN_MIN_INTERVAL_SECONDS` | `5` | minimum gap between request starts per domain, all workers |
| `MAX_RETRY_AFTER_SECONDS` | `300` | cap on a `Retry-After` wait |
| `DOMAIN_FAILURE_THRESHOLD` | `5` | consecutive failure outcomes before a domain is paused |
| `DOMAIN_PAUSE_SECONDS` | `600` | length of that pause |
| `FETCH_TIMEOUT_SECONDS` | `20` | per-request timeout |
| `FETCH_MAX_BYTES` | `5242880` | response size cap (5 MiB) |
| `ALLOWED_PORTS` | `80,443` | ports the scraper may request |
| `COMPOSE_INTERNAL_HOSTS` | empty | extra host names refused as internal (bare names are always refused) |
| `FETCH_EXTRA_HOSTS` | empty | hosts allowed for redirects and scraped links besides the active sources |
| `CONTRACTS_DIR` | `<repo>/contracts` | JSON Schemas used for validation |
