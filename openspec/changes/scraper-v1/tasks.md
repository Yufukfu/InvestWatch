# Tasks

Each group from 2 on is one commit. Its first task is the failing test and its last is the mutation check (`iw-commit-cycle` step 3), completed as `mutations: N tried, N caught` (or `mutations: n/a, <reason>`). Groups 1 and 6 are docs, agreements and one spike: no test, no mutation check. Tests that need Redis run against a Redis started with `docker run` or compose.

## 1. ADRs and agreements

- [x] 1.1 Read the installed noble-tls, curl_cffi and httpx APIs and the in-house crawler repos; write ADR 0101 (`noble-tls`, `curl_cffi` fallback, Python 3.12); docs-check passes
- [x] 1.2 Write ADR 0102 (`arq`); ADR 0103 stays criteria-only and is decided in `scraper-v2`; docs-check passes
- [ ] 1.3 Agree with C on the `scrape_meta.scraper` value for a TLS-impersonating client (v1 enum `playwright|httpx|api|manual`; field not required; interim proposal `httpx` plus `scrape_meta.client`, or a v1 enum addition with `IW_CONTRACT_CHANGE=1` and a version bump); record in ADR 0101 and `contracts/`. Blocks nothing
- [x] 1.4 Spike (no production code): header order, manual redirects and IP pinning work, the size cap cannot abort mid-stream (spec adjusted), older Chrome profiles are reset by KNF, the library updater is unpinned; results in ADR 0101 Consequences

## 2. Skeleton, parser, site registry, error model

- [x] 2.1 Failing test, then `scraper/` package with pinned deps on Python 3.12, a pytest setup and a Dockerfile whose context includes `contracts/` and that downloads the pinned `tls-client` 1.18.1 release asset for the image's platform by tag (not through the `noble-tls` updater), verifies its sha256, writes the `.version` file and fails the build otherwise, on a Debian/Ubuntu base, and the tests run on Python 3.12 there; `pytest scraper` runs green in the image (shared sync commit incl. `types.py`; image builds, 10 tests green; mutations: 6 tried, 6 caught)
- [x] 2.2 Save the real KNF warnings page as a fixture (`scraper/tests/fixtures/`), plus article, no-title, windows-1250, empty and malformed fixtures; failing tests, then the parser (title with `<h1>` fallback, `canonical_url`, link filtering); the parse scenarios pass
- [x] 2.3 Failing tests, then the host-keyed parser registry with the generic parser as default; the registry scenarios pass
- [x] 2.4 Failing tests, then typed `JobError` with the closed reason set, an in-memory sink, the JSON logger and redaction of `user:pass@` URLs; the closed-set and string-level no-credentials tests pass
- [x] 2.5 Mutation check; `mutations: 26 tried, 26 caught`

## 3. Fetch layer (single attempt)

- [x] 3.1 Failing tests, then `fetch(url, identity, proxy)` with timeout, manual redirect hops, streamed-to-file body with the size cap checked on the transferred size, IP pinning, non-HTML rejection and charset decoding, against a local stub server; the timeout, http_error, no-retry, oversized, non-HTML and charset scenarios pass. Manual probe of the KNF page recorded in the AI log
- [x] 3.2 Failing tests, then block detection (403, 429, captcha marker including a 200 block page, empty body); the blocked scenarios pass
- [x] 3.3 Mutation check; `mutations: 59 tried, 59 caught`

## 4. Identity, proxy, politeness (Redis)

- [x] 4.1 Failing tests, then the identity table (lowercase header order per browser version, one version constant for user agent, `sec-ch-ua` and TLS profile) with a load-time pairing check, and a fresh session per attempt; the header-order test against a raw-socket stub, pairing, current profiles only, no-cookie-carry-over and identity-per-run scenarios pass
- [x] 4.2 Failing tests, then the proxy rotator (`per_request` default, random start, never the same twice in a row, `PROXY_COOLDOWN_SECONDS` on 407, deferral outcome when all cool, `per_session`, empty list); the proxy scenarios pass
- [x] 4.3 Failing tests, then `robots.txt` handling (401/403/404/410 allow, 429/5xx/timeout disallow, never a block signal) and a Redis token-bucket per-domain rate limit with a local fallback; the robots and cross-worker rate-limit scenarios pass
- [x] 4.4 Failing tests, then `Retry-After` (seconds and HTTP-date, cap, domain deferral in Redis) the per-domain failure cooldown driven by recorded outcomes, and the deferral outcome (the time it ends) that a run reports; the Retry-After, paused-domain and deferral scenarios pass with a fake clock
- [x] 4.5 Mutation check; `mutations: 135 tried, 135 caught` (57 for 4.1/4.2, 78 for 4.3/4.4)

## 5. Source selection and target guards

- [ ] 5.1 Failing tests, then selection of collectable `web` sources over source records with `source_kind` copied from the record and `schedule_cron = null` as manual only; the selection scenarios pass
- [ ] 5.2 Failing tests, then the URL guard (`http(s)` only, host allow-list with `www.` equivalence for redirects and scraped links); the allow-list, redirect, apex-to-www and non-http scenarios pass; `ALLOWED_PORTS` (default `80,443`, scheme default ports, redirect hops and scraped links included) with the non-web-port, default-port and configured-port scenarios
- [ ] 5.3 Failing tests, then the address guard (own DNS resolution, refused ranges incl. IPv6 and mapped forms, compose names, connect to the checked address); the internal-address and DNS-change scenarios pass with a fake resolver
- [ ] 5.4 Mutation check; `mutations:`

## 6. Closing

- [ ] 6.1 Apply the `iw-docs-update` skill (`scraper/CLAUDE.md` stack lines, your row in `.docs/STATUS.md` (split into three changes), ADRs), run docs-check, and add the `iw-ai-log` row
- [ ] 6.2 Run the `iw-pr-review` skill and fix real findings; `iw-reviewer` reports no open blocking findings

## Workflow follow-up

- Run `/openspec-archive-change` as the last commit of the branch, then stop and hand the PR body to the human. Never push or open the PR yourself.
