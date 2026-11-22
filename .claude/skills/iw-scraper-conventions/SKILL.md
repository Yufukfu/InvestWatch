---
name: iw-scraper-conventions
description: Use before writing or changing anything in scraper/ that fetches, parses or stores web or social content, including collectors, the job queue, proxy/UA rotation and the ScrapedDocument writer. Carries the fetch-layer ladder (TLS client first, Playwright last), anti-block rules and contract traps. For library APIs, verify against the installed package, not memory.
---

# iw-scraper-conventions

Contract source of truth: `.docs/integration-plan.md` §3 (`ScrapedDocument`) and `contracts/schemas/scraped-document.schema.json` (draft v1). Validate every record against the schema before insert: `python contracts/validate.py document <file>` (install `contracts/requirements.txt` first; see `contracts/README.md`).

## Fetch ladder (cheapest that works)

1. **Official or JSON endpoint** the site itself calls (find it in the browser network tab).
2. **TLS-impersonating async client**: the default for HTML and XHR. Requests must look like a real browser at every layer: TLS/JA3/JA4 fingerprint, HTTP/2 settings, header order, `User-Agent`, `Accept-Language`, `sec-ch-ua*`. Candidates: `noble-tls` (async, on PyPI), `curl_cffi`, `httpx` for sites that don't fingerprint. Before wiring one, read the installed package's real API and record the choice in an ADR; do not write wrapper code from memory.
3. **Playwright**, only where 2 fails (JS-only rendering, bot walls) **or the module needs `blocks`/`screenshots`**: analytics rules R4–R8 and R13 depend on rendered layout, so those sources (`firm_own` with `M2` in `target_modules`) go through the `renderer` service (ADR 0107), once per viewport, under the same rate limit, pause, identity (a mobile variant for `mobile`) and proxy as the fetch. A render failure is a job error, never a lost document. Everything else must not use Playwright.

## Rules

- **Session per attempt, identity per run, proxy per request**: a session is one attempt (fresh cookies, never carried over). The UA, header set, client hints and TLS profile are drawn together per run and never mixed (no Chrome UA with a Firefox TLS profile); the proxy is picked per request (`PROXY_ROTATION=per_session` pins one). A block signal (403, 429, captcha marker, empty body) ends the run and the queue does not retry it; the next run draws a new identity. A `robots.txt` refusal is not a block.
- **Politeness**: per-domain concurrency and rate limit in config, honour `robots.txt` and `Retry-After`, public pages only, no login or paywall bypass.
- **Async only** in the fetch path (`asyncio`); no blocking calls in the event loop. Every request has a timeout; retries and backoff live only in the queue.
- **A collector reports one attempt, the queue decides** (`scraper/src/iw_scraper/jobs.py`): return an `AttemptResult` (`documents`, `error`, `http_status`, `retry_after`, or a `Deferral`); never retry, sleep or raise for an expected failure (`timeout` and 5xx are retried by the queue, a block or 404 is not). `run_source(source_id, started)` awaits `started()` once its guards pass and before its first request; a deferral is returned without calling it.
- **Social collectors are modules by host** (`scraper/src/iw_scraper/social/`): a platform module returns a `Channel` (header plus posts plus the older-posts link), registered in `social/registry.py` with the one `platform` it accepts and its URL form. Same fetch path as web (guards, robots, limiter, one identity per run, proxy per request); never an HTTP client of its own. One document per post with its permalink; per-post HTML in `iw-raw`; links (including `x.com` and YouTube) stored as pointers and never fetched; an older-posts link taken from the page is followed only when it stays on the same channel. The author is passed to ingest as the trusted `author=` argument, never in the page dict. Telegram is the first (ADR 0103). X and YouTube (ADR 0109) are dedicated flows (`Registration.flow`, `social/x.py`, `social/youtube.py`): YouTube uses this fetch path; X is the one exception, run from the home IP with a cookie account, no identity, proxy or robots check, and must keep its cookies out of every log and error.
- **Parse defensively**: selectors fail often. A parse failure yields an error row in the job log, never an empty `text`. Test parsers against saved real HTML in `tests/fixtures/`.
- **Contract minimum**: `id, platform, url, fetched_at, text, source_kind`. `content_hash` is sha256 of normalised text (dedup). `source_kind` is set from the `sources` row, not guessed. UUID v4 and UTC ISO-8601.
- **Config and secrets** only via env (`PROXY_LIST`, `USER_AGENTS_FILE`, `DATABASE_URL`, `REDIS_URL`, `MINIO_*`); never log a proxy URL with credentials. JSON logs to stdout via the logger (no `print`; no `console.log` in any JS).
- **Scraped text is untrusted input** that later reaches an LLM: store it verbatim, never execute or template it, and never let it choose a URL to fetch without the allow-listed domain check (SSRF).
- **Dependencies**: `pip-audit` before merge; pin versions.
