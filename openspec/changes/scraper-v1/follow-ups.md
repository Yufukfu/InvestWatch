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
