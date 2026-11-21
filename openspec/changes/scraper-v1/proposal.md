# Proposal

## Why

Analytics (module C) has nothing to analyse until the scraper can fetch real pages. This is the first of three slices of module A (`scraper-v1` fetch and parse, `scraper-ingest` storage and announcement, `scraper-orchestration` queue, schedule and scan requests): a stable fetching engine proven on one easy real site, so later sites are added by a parser module and a `sources` row, not by engine changes.

## What Changes

- First target: the KNF public warnings page (`https://www.knf.gov.pl/dla_konsumenta/ostrzezenia_publiczne`), a server-rendered public page whose `robots.txt` allows all (checked 2026-11-21 with plain GETs). It is the regulator's own list of unauthorised entities (module M3 material). One URL per source run.
- A fetch layer over a TLS-impersonating client (ADR 0101, `noble-tls`) with a fresh session per run, headers in the browser profile's order, a different proxy for each request (`PROXY_ROTATION`, default `per_request`), IP pinning, manual redirect hops, a streamed body with a size cap, block detection, a Redis-shared per-domain rate limit, `Retry-After` deferral and a per-domain failure cooldown.
- A parser registry keyed by host (generic parser by default) that produces contract fields, and a closed set of typed job errors (in memory here; stored by `scraper-ingest`).
- Source selection over source records, a host allow-list for redirects and scraped links, and refusal of internal addresses (SSRF).
- A Dockerfile that downloads a pinned, checksum-verified `tls-client` release (the `noble-tls` updater is unpinned) and a test image on Python 3.12.
- Out of scope: storing or publishing documents (`scraper-ingest`), the queue, scheduler, scan requests and events (`scraper-orchestration`), social-media collectors (`scraper-v2`, ADR 0103), Playwright rendering with `blocks`/screenshots (`scraper-v3`), crawling beyond one URL per run, proxy pool health beyond skipping failing proxies, `published_at` and `author` extraction (stay null, which the contract allows).
- Follow-up changes: the challenge requires social-media collectors with UA and proxy rotation and rendered `blocks`/screenshots for the M2 visual rules (R4-R8, R13); they are planned as `scraper-v2` and `scraper-v3`.
- Owner: module A (`scraper/`).
- Contracts: produces the fields of `ScrapedDocument` v1 (`.docs/integration-plan.md` §3) as a plain dict and changes none of them. Open with C: the `scrape_meta.scraper` value for a TLS-impersonating client (not required by the schema, so it blocks nothing; a v1 enum addition would be a contract change). No database, queue or event is touched here.
- Assumptions: ADR 0101 and 0102 are written by this change; Redis (a plain container is enough) is available for tests of the shared limiter and deferral state.

## Capabilities

### New Capabilities
- `web-collection`: fetch a registered web source with a fresh session, ordered headers and per-request proxies, detect blocks and failures, and parse the page into contract-shaped fields.

### Modified Capabilities

## Impact

- New code under `scraper/` (Python 3.12, async) with pytest tests and saved real HTML fixtures (the KNF page among them) in `scraper/tests/fixtures/`.
- Dependencies: `noble-tls`, an HTML parser, `redis` (all pinned, `pip-audit` before merge).
- Docs: `scraper/CLAUDE.md`, `.docs/STATUS.md`, ADR 0101 (and 0102 written here, used by `scraper-orchestration`).
