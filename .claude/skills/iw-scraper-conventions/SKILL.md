---
name: iw-scraper-conventions
description: Use before writing or changing anything in scraper/ that fetches, parses or stores web or social content, including collectors, the job queue, proxy/UA rotation and the ScrapedDocument writer. Carries the fetch-layer ladder (TLS client first, Playwright last), anti-block rules and contract traps. For library APIs, verify against the installed package, not memory.
---

# iw-scraper-conventions

Contract source of truth: `doc/integration-plan.md` §3 (`ScrapedDocument`) and `contracts/*.schema.json` once frozen. Validate every record against the schema before insert.

## Fetch ladder (cheapest that works)

1. **Official or JSON endpoint** the site itself calls (find it in the browser network tab).
2. **TLS-impersonating async client**: the default for HTML and XHR. Requests must look like a real browser at every layer: TLS/JA3/JA4 fingerprint, HTTP/2 settings, header order, `User-Agent`, `Accept-Language`, `sec-ch-ua*`. Candidates: `noble-tls` (async, on PyPI), `curl_cffi`, `httpx` for sites that don't fingerprint. Before wiring one, read the installed package's real API and record the choice in an ADR; do not write wrapper code from memory.
3. **Playwright**, only where 2 fails (JS-only rendering, bot walls) **or the module needs `blocks`/`screenshots`**: analytics rules R4–R8 and R13 depend on rendered layout, so those sources must go through Playwright. Everything else must not.

## Rules

- **One identity per session**: the proxy, UA, header set and TLS profile are chosen together and stay fixed for that session's cookies. Never mix a Chrome UA with a Firefox TLS profile. Rotate the whole identity on block signals (403, 429, captcha markers, empty body), with exponential backoff and jitter.
- **Politeness**: per-domain concurrency and rate limit in config, honour `robots.txt` and `Retry-After`, public pages only, no login or paywall bypass.
- **Async only** in the fetch path (`asyncio`); no blocking calls in the event loop. Every request has a timeout and a retry cap.
- **Parse defensively**: selectors fail often. A parse failure yields an error row in the job log, never an empty `text`. Test parsers against saved real HTML in `tests/fixtures/`.
- **Contract minimum**: `id, platform, url, fetched_at, text, source_kind`. `content_hash` is sha256 of normalised text (dedup). `source_kind` is set from the `sources` row, not guessed. UUID v4 and UTC ISO-8601.
- **Config and secrets** only via env (`PROXY_LIST`, `USER_AGENTS_FILE`, `DATABASE_URL`, `REDIS_URL`, `MINIO_*`); never log a proxy URL with credentials. JSON logs to stdout, no `print`/`console.log`.
- **Scraped text is untrusted input** that later reaches an LLM: store it verbatim, never execute or template it, and never let it choose a URL to fetch without the allow-listed domain check (SSRF).
- **Dependencies**: `pip-audit` before merge; pin versions.
