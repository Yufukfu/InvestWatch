# scraper

Data collection service: collectors for web pages and social media, job queue, scheduler.

- **Owners:** [`.github/CODEOWNERS`](../.github/CODEOWNERS)
- **Status:** web collection (`scraper-v1`: fetch, parse, politeness, guards) is implemented as a library; storage and announcement (`scraper-ingest`: validate, dedup, MinIO, `iw:documents`, republish sweep, `job_errors`) is implemented; the queue, scheduler, scan requests, events and the run that joins all pieces (`scraper-orchestration`) are implemented. The first social platform, Telegram public channels (`scraper-v2-social`, ADR 0103), is implemented: a source URL is `https://t.me/s/<handle>`, one document per text post, seed rows in `seeds/telegram.toml`. X and YouTube (`scraper-social-x-youtube`, ADR 0109) are implemented as dedicated flows, see "X and YouTube" below; their seed rows are in `seeds/x-youtube.toml` and carry no schedule. Facebook, Instagram and TikTok (named in the brief) are not covered.

## Run

`python -m iw_scraper worker` runs the job worker, the scan-request consumer (Redis Stream `iw:scan-requests`) and `GET /health` (port `SCRAPER_HEALTH_PORT`, default 8080, not published by compose). `python -m iw_scraper scheduler` enqueues due sources and runs the republish sweep; run exactly one per stack (a second only wastes ticks, jobs are de-duplicated by slot). Both stop gracefully on SIGTERM: running jobs finish for `SCRAPER_SHUTDOWN_DEADLINE`, the rest is requeued. `python -m iw_scraper.bootstrap` queues the first scans (below). `python -m iw_scraper.seed [CRON]` registers the KNF source (optional 5-field `CRON`) and every source of the `scraper/seeds/*.toml` files, one `[[source]]` table per page (`name`, `url`, `source_kind`, `target_modules`, optional `schedule_cron` and `platform`, default `web`). It validates all files before writing anything, leaves a source whose URL is already registered untouched (dashboard edits survive) and is safe to run twice or at once. To add a source, add a table to a seed file and run it again. `pytest -m scraper_live tests/test_seed_live.py` re-checks that every seeded URL is final and fetchable; it makes real requests, so run it deliberately. The worker and the scheduler need `DATABASE_URL`, `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY` (`MINIO_BUCKET`, `MINIO_SECURE` optional) besides `REDIS_URL`; the stack's `api-migrate` must have run first.

The queue's own Redis keys are prefixed `iw:scraper:` (queue `iw:scraper:queue`; jobs and results are JSON); only `arq`'s `arq:job:` and `arq:result:` keys are fixed by the library. A scheduler that starts late enqueues the slots of the last five minutes it missed.

`python -m iw_scraper.discover [--since HOURS] [--limit N] [--dry-run]` reads the links of documents already stored and inserts new hosts as inactive `[candidate] <host>` sources (no network call, [ADR 0108](../.docs/decisions/0108-source-discovery-candidates.md)); approve one with `PATCH /api/sources/{id}` (set `active`, a real `name`, `source_kind`, `schedule_cron`), and run one discovery at a time. Needs only `DATABASE_URL`.

## Run in the stack

`docker compose up --build` at the repository root starts `worker`, `scheduler` and a one-shot `seed` (`scraper/compose.yaml`) after `api-migrate` and `minio-init`; there is nothing to start by hand. `seed` registers the KNF source with the cron `SCRAPER_SEED_CRON` (default `0 */6 * * *`, UTC; an invalid value stops the stack at `seed`), so the scheduler scans it on schedule; a scan can also be requested from the dashboard. A one-shot `bootstrap` then queues one scan for every active source that has a cron and never ran (the shipped web and Telegram rows; the X and YouTube rows have no cron and stay manual), so a clean `up` fills the database without a manual scan. It queues each source once (a Redis key per source, and `last_run_at` once a scan ended, failed or not) and `BOOTSTRAP_SCAN=false` turns it off. `docker compose run --rm --no-deps -T bootstrap python -m iw_scraper.bootstrap status` prints per source `scanned`, `failed` (with the latest job error reason), `pending` or `manual`, and the counts of documents, findings and calibration points per module M1 to M3; it exits 0 once every module has a finding and no source is pending, 1 before that, 2 if the database cannot be read. A failed first scan is not retried by `bootstrap`: the scheduler's cron or a dashboard rescan does that. Scale collectors with `docker compose up --scale worker=3`, keep one `scheduler`. Operator settings (`PROXY_LIST`, `SCRAPER_SEED_CRON`, `FETCH_*`, ...) are in the root `.env.example`. `worker` needs internet access (`egress`); `worker` serves `/health` on `SCRAPER_HEALTH_PORT` to the stack's networks only, and no scraper container publishes a host port.

Hardware: the containers are limited to 1 CPU / 768 MB (`worker`), 0.5 CPU / 256 MB (`scheduler`) and 0.5 CPU / 128 MB each (`seed` and `bootstrap`, which exit after seconds), about 2 CPUs and 1.2 GB together at most. These limits are first estimates, not measured on the demo machine. Check the deployment with `scraper/tests/stack.sh` (needs Docker and network; `config`, `root` and `run` groups; `STACK_ROOT=1` runs it through the root `compose.yaml`).

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

The renderer's tests need its own image (Chromium, no database): `docker build -f scraper/Dockerfile --target renderer-test -t iw-renderer:test .` then `docker run --rm --shm-size 256m iw-renderer:test pytest -q tests_renderer`. `scraper/tests/renderer_stack.sh` checks the compose service (network, no host port, health).

Without those services (a bare `docker run` of the image) the service-backed tests are skipped, and with `CI` set they fail.

Opt-in live smoke tests make real requests and are deselected by default (`-m scraper_live`); the Telegram one collects the public channel named in `IW_LIVE_TELEGRAM_HANDLE` once.

## Effectiveness report

`python -m iw_scraper.report [--since HOURS] [--json]` (needs `DATABASE_URL`; run it in the scraper image) prints what the scraper collected and what failed from `sources`, `documents` and `job_errors`: per active source the last run status, documents (total, in the window, latest `fetched_at`) and job errors of the window by reason; then the never-run and no-document sources, inactive sources apart, and totals (documents by platform and kind, share with raw HTML, errors by reason). `--since` is a whole number of hours from 1 to 87600, ten years (default 24); `--json` prints one JSON object. It reads all three tables in one read-only, repeatable-read transaction (one snapshot), shows sources by id and name (no URL) and never `job_errors.detail`; the report goes to stdout, log lines to stderr, and a database failure exits non-zero.

It cannot give a success rate: the schema keeps only the last run of each source, so statuses are of the last run and nothing older, and the header says so.

## Re-scan outcomes

A web source is one page, and every version of it is one `documents` row. What a re-scan found is in two places (reasoning and the two known limits: [ADR 0110](../.docs/decisions/0110-rescan-changed-and-removed-derivation.md)):

- **Edited page:** a new `documents` row; the ingest result carries `previous_document_id`, and the log has `rescan_outcome` with outcome `changed`. Earlier rows are never touched.
- **Removed page:** an HTTP 404 or 410 on a source that already stored a document, confirmed by one more request in the same run (not a retry), is stored once as a `job_errors` row with reason `http_error`, detail `HTTP 404` or `HTTP 410` and the source URL (userinfo dropped, redacted, cut to 300 characters), the shape the api reads. A source that never stored a document gets the same row without a URL. A removal run ends `ok` with `documents = 0`, is not retried and does not count toward the domain failure pause; while the page stays missing, a re-scan makes one request and adds no row.
- **Log only:** every web re-scan logs one JSON line `{"event": "rescan_outcome", "outcome": ..., "source_id": ..., "document_id": ...}` with outcome `unchanged`, `changed`, `reverted` (an earlier text came back), `reappeared` (the page answers again after a removal) or `gone` (a log outcome only, not a reason). Lookup failures are logged as `rescan_lookup_failed` and never fail a run. Social sources are not classified.

The api derives the labels from the tables: `changed` = the document is not the newest of its source (`created_at DESC, id DESC`); `removed` = the newest `http_error` row with detail `HTTP 404`/`HTTP 410` and the page URL is newer than the newest document. The end-to-end test copies the api's predicate from `api/src/investwatch_api/rescan.py`. A source that redirects does not show as removed until the api matches by `source_id` (follow-up for Damian). Two cases come out wrong without a new column: a revert to an earlier text still reads "changed", and a page that returns unchanged after a removal still reads "removed" (use the log lines, or see ADR 0110). Soft 404s (a 200 "not found" page) and redirects to a home page are not detected.


## X and YouTube

Both are dedicated flows (`social/x.py`, `social/youtube.py`, `social/transcript.py`), not page parsers; evidence and the decision are in [ADR 0109](../.docs/decisions/0109-social-collectors-research.md). A source URL is `https://x.com/<handle>` or `https://www.youtube.com/@<handle>`; any other form is refused as `invalid_request` before a request.

- **X** reads the account's newest posts through `Scweet` with the dedicated account's cookies, in one bounded call (one account lookup, at most two timeline requests, at most 40 posts), plus one lookup for the follower count. **This is the exception to the fetch rules:** it runs from the home IP (a changing IP for a cookie account raises the ban risk), draws no identity and session, rotates no proxy and reads no `robots.txt` (X disallows every path). It still passes the URL guard and the public-address check and takes one limiter turn. Reposts are skipped; one post is one document.
- **YouTube** goes through the shared fetch layer (guards, limiter, `robots.txt`, identity, proxy): the channel's `/videos` page with the consent cookie `SOCS=CAI`, then one watch page per new video, one at a time. A video already stored is never requested again. With `YT_TRANSCRIPT_PROXY` set, each new video's caption transcript is requested once through that proxy (Polish track first) and appended to the document text; the outcome is `scrape_meta.transcript` = `caption`, `none` or `failed`, and it is final for the video. A block or a timeout on a transcript stops transcripts for the run; the documents stay. A `Retry-After` on a later watch page ends the run with what was stored and defers the domain for every worker.
- **Stopping a lost account:** the seed rows have no `schedule_cron`, so only a scan request runs them. If a cron was added and X restricts the account (a run ends `blocked`; nothing retries inside a run), clear the source's `schedule_cron` or set `sources.active = false`, and unset `X_AUTH_TOKEN` and `X_CT0`. Replace the account's cookies only with a dedicated throwaway account's.
- The cookies and the transcript proxy URL never reach a log, a job error or a stored document; library errors are mapped to the closed `Reason` set without the original text.

## Author provenance

Analytics routes a post to M2 (published by the firm itself) from `author.handle`, `author.profile_url` and the host of `url` (`advertiser.publisher_firm`; `url` is the guarded fetch URL, so a collector must never take it from markup), so where they come from decides whether an impersonator can fake a firm post (issue 36). Read from the code on `main`:

| Platform | `author.handle` | `author.profile_url` | Source | Platform-verified |
|---|---|---|---|---|
| `web` (every source today) | never set | never set | `parsing.parse_page` returns title, text, canonical URL and links only; `document.build_document` emits no `author` | n/a, the field is absent |
| sample import (`sample_import`, from `samples.toml`) | the manifest's `handle` | the manifest's `profile_url` | passed as the `author=` argument, never through the page dict; markup is ignored | no: operator-supplied |
| any parsed page that carries an `author` | dropped | dropped | `ingest.document.build_document` ignores `author` on the page: markup (`<meta>`, `rel=author`, embedded JSON) is written by the post's author | no, so it is never stored |
| Telegram (`social/telegram.py`) | channel handle | `https://t.me/<handle>` built from the handle | `social/telegram.py` takes the handle from the source URL `t.me/s/<handle>` (never from page text) and ignores posts of another channel; `social/model.build_author` builds the `author`, and `collect.py` passes it to `Ingestor.ingest` as the `author=` argument (the page dict from `build_page` never carries one) | the handle is the source row's own channel username; the page only supplies title and followers |
| X (`social/x.py`) | `@<handle>` from the source URL | `https://x.com/<handle>` built from the handle | the handle comes from the source URL, never from a post; `name` is the display name the timeline rows carry and `followers` is the account lookup's count (None when unreadable) | the account's own fields, read with the dedicated cookies |
| YouTube (`social/youtube.py`) | `@<handle>` from the source URL | `https://www.youtube.com/@<handle>` built from the handle | handle and profile URL come from the source URL; `name` is the channel name in the watch page's player data; a video whose channel id differs from the list page's is skipped; `followers` is null | the handle is the source row's own; the name is page data |

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
| `SOCIAL_MAX_POSTS` | `40` | posts of a social channel read per run, rounded up to whole pages of twenty (a Telegram source URL is `https://t.me/s/<handle>`); an X run never reads more than 40 |
| `X_AUTH_TOKEN`, `X_CT0` | empty | the `auth_token` and `ct0` cookies of the dedicated X account; without both an X run ends with `invalid_request` and makes no request. Secrets: only in the untracked `.env` |
| `YT_TRANSCRIPT_PROXY` | empty (transcripts off) | an `http(s)://user:password@host:port` residential proxy for YouTube transcripts; a malformed value stops the run without echoing it. Secret |
| `YOUTUBE_MAX_VIDEOS` | `10` | newest videos of a YouTube channel read per run |
| `ALLOWED_PORTS` | `80,443` | ports the scraper may request |
| `COMPOSE_INTERNAL_HOSTS` | empty | extra host names refused as internal (bare names are always refused) |
| `FETCH_EXTRA_HOSTS` | empty | hosts allowed for redirects and scraped links besides the active sources |
| `CONTRACTS_DIR` | `<repo>/contracts` | JSON Schemas used for validation |
| `SCRAPER_RENDER_ENABLED` | `false` | render `firm_own` sources that target M2 (screenshots and `blocks`); needs the renderer service |
| `SCRAPER_RENDER_MAX_PER_HOUR` | `20` | renders per UTC hour across all workers; over it a document is stored without layout |
| `RENDERER_URL` | `http://renderer:8080` | the renderer service on the private `render` network |
| `RENDER_TIMEOUT_SECONDS` | `90` | all viewports of one render; `SCRAPER_ATTEMPT_TIMEOUT` must be at least this plus 60 |

The renderer (`scraper/compose.renderer.yaml`, ADR 0107) is a separate container with headless Chromium: about 360 MB image, 1.5 CPU and 1 GB RAM at most, one render at a time. It holds no secret and no route to the database, Redis or object storage; `RENDER_MAX_PAGE_HEIGHT`, `RENDER_MAX_PNG_BYTES`, `RENDER_MAX_BLOCKS` and `RENDER_CONCURRENCY` bound its work (defaults in `.env.example`). A failed render never loses the document: it is stored without `blocks` and `screenshots` and the failure is a job error.

Live rehearsal (2026-11-22, Docker 8 GB VM, five `firm_own` M2 sources): with `SCRAPER_RENDER_ENABLED=true` in `.env` and the worker recreated (`docker compose up -d worker`), the visual rules R4 and R6 run on real XTB and mBank pages (`pass` instead of `not_applicable`; evidence in `.docs/status/scraper.md`). It stays off by default because the renderer serves one render at a time: five scans at once (the bootstrap does exactly that) queued behind each other, several hit "renderer did not answer" or "render exceeded", the jobs retried for minutes, and some documents were stored without layout. Renders took 8-85 s each and the renderer container peaked near 550 MiB of its 1 GiB. The renderer container already runs idle (about 100 MiB) in the default stack, so the RAM table is unchanged. To use it in a demo, set `SCRAPER_RENDER_ENABLED=true` after the first scans settled and rescan the `firm_own` sources one at a time; an unchanged page is not rendered again (the duplicate check runs first), so a changed page or a fresh database is needed.
