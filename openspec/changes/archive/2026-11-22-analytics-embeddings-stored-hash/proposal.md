# Proposal

## Why

Two facts reached `analytics-embeddings` (PR #81) after its archive:
- `main` merged `analytics-stored-content-hash` (ADR 0105, issue #31). Analytics no longer computes a content hash: `Preprocessed.content_hash` is gone, and caches key on the document's stored `ScrapedDocument.content_hash`. A document without one is not cached.
- The manual task 9.4 run against a real `bge-m3` on CPU measured 4-12 s per warm call and 37 s for a cold load. With the old default of 5 s, most calls timed out and the breaker turned embeddings off.

The main spec `text-embeddings` still says the embedding cache keys on "analytics' own preprocessing hash". This change makes the spec match the merged code.

## What Changes

- **Embedding cache key:** the document's stored `content_hash`. Without one, the document is embedded but not cached.
- **`EMBED_TIMEOUT_S` default:** 15 s instead of 5 s. A value, not a spec change; recorded in `analytics/.env.example` and `analytics/README.md`.

## Capabilities

### Modified Capabilities
- `text-embeddings`: MODIFIED "Embedding cache in Redis" (the key is defined by the new requirement), ADDED "Embedding cache key".

## Impact

- Module owner: Damian (`analytics/`). No contract, REST route or event change.
- Code is already in PR #81: the merge commit `1655ec6` (stored hash) and `52907fd` (timeout).
- Out of scope: anything outside the embedding cache key and the timeout default.
