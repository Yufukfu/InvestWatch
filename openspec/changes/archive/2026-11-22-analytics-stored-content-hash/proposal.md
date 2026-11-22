## Why

Issue #31: `content_hash` has one definition, NFC (`.docs/integration-plan.md` §3, [ADR 0105](../../../.docs/decisions/0105-content-hash-normalisation.md), PR #44). The scraper computes it and stores it on `documents`, where it is the dedup key. Analytics still computes its own hash from its NFKC-normalized text in `preprocess()`, so text with compatibility characters (ligature `ﬁ`, superscript `²`, full-width digits) gets a different value there. Its only reader is the LLM response cache key (`rules/engine.py` passes `ctx.pre.content_hash` to the judge, ADR 0309). Damian decided that analytics reads the stored value and does not compute one.

## What Changes

- `analytics/src/investwatch_analytics/preprocessing.py`: remove `content_hash()` and the `Preprocessed.content_hash` field. The document's `content_hash` is `ScrapedDocument.content_hash`, as loaded from the `documents` row (or the stream message) and never recomputed. When a document has none (the field is optional in the contract), analytics leaves it absent.
- NFKC `normalize()` stays: rule matching, language guess and excerpts.
- LLM judge: the cache key uses the document's stored `content_hash` (`rules/engine.py` passes `ctx.doc.content_hash`). A document without one bypasses the cache (no read, no write), so a missing hash never becomes a key that documents share. The scraper writes a hash for every row, so the worker always caches; the CLI on a document without one does not.
- `document-analysis` requirement "Preprocessing" MODIFIED: no hash computed in analytics; the stored value is used as is.
- `.docs/analytics-plan.md` §2 row 1 and §7 cache line, ADR 0309's cache-key line: NFKC is for matching only; `content_hash` is the stored NFC value (ADR 0105).

## Capabilities

### New Capabilities
- none

### Modified Capabilities
- `document-analysis`: preprocessing no longer computes a content hash; the stored one is used.
- `llm-analysis`: the response cache is keyed by the stored `content_hash`; a document without one is not cached.

## Impact

- Owner: Damian (`analytics/`). Touches no contract file, REST route or event: `ScrapedDocument.content_hash` keeps its schema and definition; analytics only stops producing a second, divergent value.
- Callers: the LLM judge was the only reader of `Preprocessed.content_hash` (checked with `git grep`). Cache entries written under the old NFKC key are no longer hit and expire with their TTL; findings, events and storage do not change.
- Out of scope: `scraper/` (Adam), `contracts/mocks/generate_mocks.py`, whose `sha()` lowercases before hashing (`content-hash-definition` follow-up 4; its own decision, contracts are frozen and nothing dedups on the mocks).
