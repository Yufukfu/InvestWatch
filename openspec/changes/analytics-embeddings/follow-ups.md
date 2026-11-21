# Follow-ups

## Review findings

| # | Source | Item | Disposition |
|---|---|---|---|
| R1 | review group 1 | https-with-key rule had no accepting test | `fix-here` (eecc55b) |
| R2 | review group 1 | bad port, `:abc` and whitespace in `EMBED_BASE_URL` passed startup | `fix-here` (eecc55b). `_check_base_url` (LLM, analytics-llm-p0) has the same gap: told the coordinator |
| R3 | review group 1 | key-leak test half tautological | `fix-here` (eecc55b) |
| R4 | review group 1, PLAUSIBLE | `ollama` host name counts as local, so a key may go over plain http to it | `wont-fix`: same accepted rule as the LLM (`_LOCAL_HOSTS`), compose service name |
| R5 | review group 1, can't verify | callers must pass the real `llm_doc_budget_s` to `EmbedSettings.from_env` (default 0 skips the combined check) | `fix-here` in group 9 (worker wiring) |
| R6 | review group 2 | huge integer values (OverflowError) and deep JSON nesting (RecursionError) escaped untyped | `fix-here` (both are `EmbedMalformed`). `llm/client.py:_content` has the same RecursionError hole: told the coordinator |
| R7 | review group 2 | a lone surrogate in scraped text raised UnicodeEncodeError before the request | `fix-here`: ASCII-escaped JSON body |
| R8 | review group 2 | timing tests counted SSL context setup | `fix-here`: client built before the clock starts |
| R9 | review group 2 | worst-case wall time is about connect (3 s) + 2 x `EMBED_TIMEOUT_S` (header wait plus one chunk wait), not timeout + 1 s; the claim-idle check sums only one timeout | `docs`: same behaviour as the LLM client; with the defaults (5 s) the worst case is 13 s, well inside the 60 s claim idle time. Revisit together with the LLM budget in analytics-llm-p0 group 10 |
| R10 | review group 2, PLAUSIBLE | gzip response could inflate past the size cap inside one chunk | `fix-here`: `Accept-Encoding: identity` |
| R11 | review group 2 | the guard fires on send, not on build | `fix-here`: spec wording matches the guard (any request to a non-stub host fails the test); the shared conftest guard is analytics-llm-p0's |
| R12 | review group 2, uncovered | no test pins `CONNECT_TIMEOUT_S` or `trust_env=False` | `wont-fix` for now: mirrors the LLM client, which has the same gap |
| R13 | group 3 | `analytics-llm-p0` has no breaker yet (its group 10), so `embeddings/breaker.py` is a minimal one of our own | `new-item` after llm-p0 group 10: merge into one generic breaker if its class is shareable |
| R14 | review group 3 | a non-UTF-8 cached value raised UnicodeDecodeError out of `embed` through a `decode_responses=True` client | `fix-here` |
| R15 | review group 3, PLAUSIBLE | an oversized planted cache value was decoded into floats before the length check | `fix-here`: length check restored before decoding |
| R16 | review group 3, PLAUSIBLE | an unexpected exception in a half-open trial left the breaker shut for good and escaped `embed` | `fix-here`: catch-all counts as unavailable |
| R17 | review group 3 | failed trial not tested above threshold 1 | `fix-here` |
| R18 | review group 3, can't verify | callers must pass a per-document, non-empty `content_hash`; Redis latency until the 1 s socket-timeout client (group 9) | `fix-here` in groups 7 and 9 |
