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
| R19 | review group 4 | common posts dropped: inflected `forexie`/`Nasdaqu`, compounds `CFDs`/`S&P500`/`BTCUSD`/`#forexsignals`, `tradować`, `finansowa`, `dochód`, WIG/GPW, ETH/USDT, `return`/`income` | `fix-here`: stems and terms added; `forexpo`/`cfdx` now pass too (recall first) |
| R20 | review group 4 | regex scan took seconds to tens of seconds on hostile 2 MB text | `fix-here`: only the first 200k characters are scanned, plus a first-letter lookahead (worst measured about 1.6 s under load) |
| R21 | review group 4, PLAUSIBLE | prefixes not normalized, unknown YAML keys ignored, bare `*` word accepted | `fix-here` |
| R22 | review group 4 | tests that could not fail (embedder always None, redundant repr check), no test for uppercase or diacritic terms or the `wy` prefix | `fix-here` |
| R23 | review group 4 | if group 5 (stretch) is cut, no test covers vocabulary-free investment posts: they are dropped by design | `docs`: noted in design §4 as the known cost of the dictionary-only gate |
| R24 | review group 6 | a spam flood made each `observe` read every id of 32 growing buckets (O(N) per copy, O(N²) total) and the buckets never expired | `fix-here`: `SRANDMEMBER` sample of 64, no `SADD` to a bucket of 256 or more |
| R25 | review group 6, PLAUSIBLE | memory estimate in design was about 8x too low | `docs`: design corrected; url capped at 2048 characters |
| R26 | review group 6, PLAUSIBLE | the group outlived its original's keys, so `original_url` became null | `fix-here`: a new member refreshes `meta:{gid}` and `doc:{gid}`; the summary sentence (group 8b) also skips a null `original_url` |
| R27 | review group 6 | a redelivered original reported a similarity to a document of another group | `fix-here` |
| R28 | review group 6 | determinism only checked in one process; estimate-dependent tests had no preconditions; long-text test timing only | `fix-here`: golden signature and bucket key, precondition asserts, shingle-count bound |
| R29 | review group 6 | two workers observing near-identical documents at the same instant can both become originals | `wont-fix`: one missed grouping and possibly one extra alert, no corruption (MULTI/EXEC pipeline) |
