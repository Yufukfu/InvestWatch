# Follow-ups

| # | Source | Finding | Disposition |
|---|---|---|---|
| 1 | `content-hash-definition` follow-up 1 | `.docs/analytics-plan.md` §2 row 1 read as an NFKC hash | `fixed`: this change (row 1 says NFKC is for matching only and `content_hash` is the stored NFC value, ADR 0105) |
| 2 | `content-hash-definition` follow-up 2 (issue #31) | analytics computed its own NFKC `content_hash` in `preprocessing.py`; the `document-analysis` "Preprocessing" requirement said so | `fixed`: this change (hash removed from analytics, requirement MODIFIED) |
| 3 | `content-hash-definition` follow-up 4 | `contracts/mocks/generate_mocks.py` `sha()` lowercases and applies no NFC, so the mock `content_hash` values do not match the definition | `new-item`: stays Damian's own decision (contracts are frozen; nothing dedups on the mocks); not part of this change |
| 4 | validation | `openspec/changes/findings-explorer-review-fixes/` (Kacper's, from PR #39) is still unarchived on `main`; reported as failing `openspec validate`, but on `main` at 2174d23 `validate --all --strict` with 2.1.1 passes (31 passed, 0 failed) | `new-item`: Kacper's change, not touched here; archiving it is his call |
| 5 | implementation | on current `main` the LLM cache key (`analytics-llm-p0`, ADR 0309) read `Preprocessed.content_hash`, so the hash had a reader after all | `fixed`: this change keys the cache on the stored hash and bypasses the cache without one (`llm-analysis` MODIFIED, ADR 0309 line amended) |
