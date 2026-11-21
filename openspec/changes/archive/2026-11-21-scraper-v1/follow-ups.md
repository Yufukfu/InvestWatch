# Follow-ups

Out-of-scope review findings and "declined to judge" items, one disposition each (`fix-here`, `new-item`, `wont-fix`, `docs`).

| Finding | Source | Disposition | Where |
|---|---|---|---|
| `redact` stops at the first `/` or whitespace, so an unencoded `/` or space in a proxy password is not redacted. Widening the pattern would over-redact query strings containing `@`; the real remedy is to log only the proxy identifier, never the raw URL | review of e41cd56, finding 2 | fix-here | task 4.2: the rotator exposes an identifier only, with a test that no raw proxy URL reaches a log or job error |
| `canonical_url` and `links` come from scraped content and may name any host; they are stored, not fetched | review of e41cd56, finding 3 | fix-here | task 5.2: the allow-list guard is tested directly on a canonical URL and a scraped link |
| Charset, size cap, non-HTML rejection and block detection at fetch level | review of e41cd56, declined to judge | fix-here | tasks 3.1 and 3.2 |
| `final_url` handed to the parser must be the URL after the redirect guard | review of e41cd56, declined to judge | fix-here | task 3.1 (`fetch` returns the final URL; parse uses it) |
| lxml behaviour on very deep or huge documents | review of e41cd56, declined to judge | fix-here | task 3.1 size cap bounds the input |
| Database sink and proxy identifier production | review of e41cd56, declined to judge | docs | other changes: `scraper-ingest` (sink), task 4.2 (identifier) |
| The test command in `scraper/CLAUDE.md` and the session notes (`python:3.12-slim` plus `pip install`) no longer covers `test_fetch.py`: it needs the native tls-client library, which only the image has (`docker build -f scraper/Dockerfile --target test`, mount `scraper/` over `/app/scraper`) | task 3.1 | fix-here | task 6.1: document the image-based test command in `scraper/CLAUDE.md` |
| A pinned run keys cookies by the IP in the request URL, so two allow-listed hosts on one IP could share cookies within that single run | review of 600cc26, finding 5 | wont-fix | one run, allow-listed hosts only, and a fresh jar every run; the spec wants cookies kept within a run |
| An `https` to `http` redirect is followed | review of 600cc26, finding 6 | wont-fix | browsers follow it too; no credentials are ever sent (URLs with userinfo are refused) and the guard still checks the hop |
| Repeated `Location` headers are joined into one invalid URL | review of 600cc26, finding 7 | wont-fix | the scheme and host floor refuses it or the client rejects it; no request reaches a wrong host |
| DNS rebinding behind a proxy | review of 600cc26, declined to judge | wont-fix | accepted in `design.md` (SSRF residual risk): `PROXY_LIST` is operator-controlled |
| No port restriction on allow-listed hosts (for example `:6379`) | review of 600cc26, declined to judge | fix-here | spec requirement "Fetch only allowed ports" (`ALLOWED_PORTS`, default `80,443`), implemented in task 5.2 |
| Content type of redirect and non-2xx bodies | review of 600cc26, declined to judge | wont-fix | those bodies are never read, so their type cannot matter |
| Supply chain of the native tls-client library | review of 600cc26, declined to judge | docs | the Dockerfile pins the release tag and verifies its sha256 (ADR 0101) |
| `proxy_identifier` is 8 hex characters of a hash, so it can collide or be guessed for a known URL | review of 050e928 | wont-fix | it is a log label, not a key: the rotator keys cooldowns by URL, and a guess needs the full URL including its credentials |
| Bound the `_request_through_proxies` loop in case a cooldown never ends | review of 050e928 | wont-fix | the cooldown is now validated finite and positive in `ProxyRotator` and `proxy_settings`, so every penalised proxy cools and the loop ends in a deferral |
| The session-close warning in `fetch` is covered by `redact` only | review of 050e928 | wont-fix | it logs the exception through the redacting logger and carries no proxy URL of its own |
| `urllib.robotparser` ignores `*` and `$` rules, so a wildcard Disallow was fetched | review of b3f9d3d, finding 1 | fix-here | confirmed on Python 3.12; replaced by `protego` 0.7.0 (RFC 9309, no dependencies), tests for `*`, `$` and longest match |
| The failure counter has no time window, so failures spread over days add up | review of b3f9d3d, finding 2 | wont-fix | the spec says "consecutive failure outcomes" with no window; a success resets it and a pause restarts it |
| `DomainGate` compares times from each worker's own clock | review of b3f9d3d, finding 3 | wont-fix | workers share one compose host; a skew only shifts a deferral by the skew. The rate limiter uses Redis `TIME` because there the spacing is the point |
| A Redis that never answers blocked `wait_turn` | review of b3f9d3d, finding 4 | fix-here | `wait_for` with `REDIS_TIMEOUT_SECONDS`, then the local fallback; tested with a hung client |
| An empty host gives the shared rate-limit key `iw:rl:` | review of b3f9d3d, finding 5 | wont-fix | the target guard refuses a URL without a host before any limiter call |
| `robots.txt` is refetched on every run and is not itself rate limited | review of b3f9d3d, declined to judge | wont-fix | v1 fetches one URL per run (design.md); the run composer in `scraper-orchestration` spaces the two requests with `DomainLimiter` |
| Lua scripts on the pinned Redis version | review of b3f9d3d, declined to judge | docs | tests ran against `redis:7`; the compose Redis image is pinned by `scraper-orchestration` |
| Scraped `canonical_url` and `links` are checked by `UrlGuard` directly, but nothing yet fetches them | task 5.2 | docs | v1 fetches one URL per run; the guard is tested on both |
| The address guard resolves with the scraper's own DNS even behind a proxy, which resolves again | task 5.3 | wont-fix | accepted in `design.md` (SSRF residual risk): `PROXY_LIST` is operator-controlled |
| NAT64, 6to4, IPv4-compatible and site-local IPv6 literals, and `192.0.0.9`, passed the address guard | review of 229c532, finding 1 | fix-here | confirmed on CPython 3.12.16; the embedded IPv4 is unwrapped and rechecked, `fec0::/10` and `192.0.0.0/24` are refused |
| `getaddrinfo` had no timeout | review of 229c532, finding 4 | fix-here | `RESOLVE_TIMEOUT_SECONDS`, a timeout is `http_error` |
| Behind a proxy the guard still resolves locally, and the proxy resolves again | review of 229c532, finding 2 | wont-fix | accepted in `design.md`; the local lookup is the check, not the connection |
| `UrlGuard`, `AddressGuard` and `target_guard` have no caller in `src/` | review of 229c532, finding 3 | docs | wiring a run (selection, guards, robots, limiter, gate, fetch) is `scraper-orchestration`; every piece takes the guard as a parameter and is tested through it |
| `www.` and the bare host count as one host | review of 229c532, finding 5 | wont-fix | required by the spec ("apex to www") |
| Spec requires the contract fields (`fetched_at`, `http_status`, `platform`, `source_kind`, `scrape_meta`) but nothing built them | whole-branch review, finding 1 | fix-here | task 5.5: `build_document`, tested against the contract schema |
| Size cap and fetch timeout were parameters only, not env settings | whole-branch review, finding 2 | fix-here | `FETCH_TIMEOUT_SECONDS`, `FETCH_MAX_BYTES` in `config.fetch_settings()`, validated and tested; like every `config.py` setting they are passed to `fetch`, `check_robots` and the limiters by the run composer in `scraper-orchestration`. The DNS, Redis and robots limits stay module constants |
| `fetch(..., guard=None)` skips the allow-list, port and address checks | whole-branch review, finding 3 | docs | `guard` is optional so unit tests can hit a loopback stub; the run composer in `scraper-orchestration` must always pass `target_guard(...)` and carries a test for it |
| ADR 0101 and 0102 had stale task numbers and a stale "not yet verified" line | whole-branch review, finding 4 | fix-here | corrected in this PR |
| A `Retry-After` of more than 4300 digits raised `ValueError` on Python 3.12 | security review, finding 1 | fix-here | digits beyond 15 are treated as the cap; tested with 5000 digits |
| `DomainGate` Redis calls had no timeout | security review, finding 2 | fix-here | `wait_for(REDIS_TIMEOUT_SECONDS)`, a hang fails the call; tested for all three methods |
| The body is capped only after it is on disk, and there is no overall deadline across hops | security review, finding 3 | wont-fix | bounded by `MAX_REDIRECTS + 1` requests of `FETCH_TIMEOUT_SECONDS` each; a size-limited `tmpfs` for `/tmp` is a compose setting for `scraper-orchestration` |
| Protego turns `*` rules into regexes and `can_fetch` is synchronous | security review, finding 4 | wont-fix | the host is on the operator's allow-list and the file is capped at 512 KiB |
| Base image has no digest, requirements have no hashes, `curl` stays in the image | security review, finding 5 | wont-fix | hackathon scope: direct dependencies are pinned and `pip-audit` is clean; the tls-client asset is pinned by sha256 |
| DNS lookups from the local resolver leave the proxy path | security review, declined to judge | wont-fix | accepted in `design.md`; an anonymity question for the product, not a security hole |
