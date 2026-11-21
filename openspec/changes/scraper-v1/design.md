# Design

## Context

This change is the fetch-and-parse half of module A: given a source record it fetches one URL with a browser-like identity and turns the page into contract fields, or into a typed job error. Storing and announcing documents is `scraper-ingest`; queueing, scheduling and scan requests are `scraper-orchestration`. Fetch-layer rules: `iw-scraper-conventions`. Scope: `proposal.md`.

## Goals / Non-Goals

**Goals:**
- Small stages (`select -> guard -> fetch -> parse`), each testable without network.
- Failures are first-class: every non-success outcome is a typed job error.
- Shared state only in Redis, so several workers behave as one.
- A site is added by a parser module and a `sources` row.

**Non-Goals:**
- Social collectors, Playwright rendering (`blocks`, screenshots), crawling beyond one URL per run, proxy pool health management.

## Decisions

- **One URL per run in v1.** A run fetches the source URL, follows redirects hop by hop and reads `robots.txt`. Scenarios about "every fetch of a run" mean that one fetch.
- **Terms.** Job = one enqueued unit for a source; attempt = one execution of it by the queue (retries make several); run = the fetching of one attempt; session = the state of one run. The run lock and `scan.*` events belong to the job; sessions and identities belong to the attempt; the domain failure count is per job final outcome. The queue, run lock and `scan.*` events (`scraper-orchestration`) belong to the job.
- **Session = one run (one attempt).** Empty cookie jar, a newly drawn identity (user agent, ordered header set, TLS profile of one browser family), nothing reused across attempts, runs or sources. The proxy is not part of the identity: it is chosen per request (`PROXY_ROTATION=per_request`, default; random start, never the same proxy twice in a row; a 407 puts that proxy on `PROXY_COOLDOWN_SECONDS`, default 90; when every proxy is cooling the attempt is deferred, not failed). Trade-off: a site that binds a session cookie to an IP can break under per-request rotation, hence the `per_session` switch.
- **Fingerprints age.** KNF reset connections for Chrome 117 and 131 profiles and accepted Chrome 146 (ADR 0101 spike), so the identity table holds only current versions, the library is pinned to a release that has them, and the opt-in live canary (task 10.5) is the staleness alarm.
- **Header order is data, not code.** The identity table lists headers lowercase in the browser's wire order, one entry per browser version, driving the user agent, `sec-ch-ua` and the TLS profile together. The order is verified on the wire with a raw-socket stub; browser DevTools show headers alphabetised and must not be used as the reference. A run blocked on every proxy is investigated as a header problem first.
- **Fetch client** behind `fetch(url, identity, proxy)`; one attempt, manual redirect hops (`allow_redirects=False`), IP pinning through `server_name_overwrite` plus `request_host_override`, body streamed to a temporary file with the cap checked afterwards (the client cannot abort mid-stream). Spike results: ADR 0101. The client choice is ADR 0101; whether it can pin the resolved IP and take explicit header order is settled by an early spike (task 3.1) before `fetch()` is built.
- **Shared state in Redis**: a per-domain *rate limit* (token bucket in a Lua script, local fallback when Redis is down, as in `hen68/cheaply-self-hosted` `shared/ratelimit.py`) that spaces request starts, `Retry-After` deferral and a per-domain failure cooldown (consecutive failure outcomes recorded by the queue). A run that meets a deferral, a paused domain or an all-proxies-cooling state reports the time it ends and does not fetch; the queue (`scraper-orchestration`) requeues it. The per-domain concurrency cap and the run lock are `scraper-orchestration`.
- **Fetch allow-list = hosts of active `sources` rows plus configured extras** (`www.` equivalent), applied to every redirect hop and every URL from scraped content, never to the source URL itself (it is on the list by construction); the source URL gets scheme and address checks. Then a refusal of private, loopback, link-local, unique-local, unspecified, multicast and IPv4-mapped addresses after our own DNS resolution, connecting to the checked address.
- **SSRF residual risk**: behind a proxy the proxy resolves DNS itself, so a rebinding answer there cannot be excluded; accepted for the hackathon because `PROXY_LIST` is operator-controlled.
- **`scrape_meta.scraper`** has no exact v1 value for a TLS-impersonating client (enum `playwright|httpx|api|manual`); it is not a required field, and task 1.3 settles it with C. This change does not pick a value in a contract file.
- **Contracts in the image**: `CONTRACTS_DIR` points at `contracts/`, which the image build context includes.
- **`documents` and the queue are not here.** A `JobError` is an in-memory value with a sink interface; `scraper-ingest` adds the database sink.

## Risks / Trade-offs

- [Client fingerprint blocked by a target] -> the `fetch()` seam allows swapping the client; a site that needs rendering is handled by `scraper-v3`.
- [Parser breaks on layout change] -> fixture tests per site, a live canary test (opt-in, outside CI) and `parse_error`/`empty_text` errors, never empty documents.
- [Per-request proxy rotation breaks cookie-bound sites] -> `PROXY_ROTATION=per_session`.
- [Redis down] -> rate limiting falls back to a process-local limiter with a warning.

## Open Questions

- None blocking.
