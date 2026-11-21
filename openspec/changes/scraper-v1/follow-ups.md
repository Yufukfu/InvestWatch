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
