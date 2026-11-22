---
when: Sun ~01:30
who: Damian
---

## What was done with AI

The `analytics-embeddings` session ran task 9.4 after opening PR #81: a throwaway pinned Ollama with `bge-m3` on a loopback port, the CLI and the pipeline on the mocks with the real model, Damian approving the one-time model download. Then it merged `main` to resolve the PR's conflicts (`analytics-embeddings-stored-hash`).

## Outcome / lesson

The real model showed what the stub tests could not: 4-12 s per warm call and 37 s cold on a loaded CPU, so the 5 s default timed out and the breaker turned embeddings off. Fixed test-first (default 15 s, pre-warm note). The merge also hit a semantic conflict: `main` removed `Preprocessed.content_hash` (ADR 0105). The embedder now keys on the stored hash and skips the cache without one, like the LLM cache. Lesson: run every model-backed feature against the real model once before calling it done.
