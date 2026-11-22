# Tasks

## 1. Stored content_hash as the embedding cache key (~20 min)

- [x] 1.1 Failing tests: the pipeline passes `doc.content_hash` to the embedder; no or empty stored hash embeds without writing `iw:emb:v1:*` (`tests/test_pipeline_embeddings.py`, `tests/test_embed_cache_breaker.py`)
- [x] 1.2 `pipeline.py` passes `doc.content_hash`; `HttpEmbedder.embed(text, content_hash: str | None)` skips the cache without one; in the merge commit `1655ec6`; tests green
- [x] 1.3 Mutation check; `mutations: 4 tried, 4 caught`

## 2. EMBED_TIMEOUT_S default 15 s (~10 min)

- [x] 2.1 Failing test: `test_defaults` expects 15 s; the default still fits the 60 s claim idle with the default LLM budget (40 + 3 + 15)
- [x] 2.2 `config.py` default, `analytics/.env.example`, `analytics/README.md` (measured latencies, cold start, pre-warm); commit `52907fd`; tests green
- [x] 2.3 Mutation check; `mutations: 1 tried, 1 caught` (the old default 5 fails `test_defaults`)

## 3. Closing

- [x] 3.1 Apply the iw-docs-update skill (`analytics/README.md`, `.env.example`, `.docs/analytics-plan.md` §7 cache key) and add the iw-ai-log row; docs-check clean
- [x] 3.2 Run the iw-pr-review skill: an `iw-reviewer` pass on the fix range, and fix real findings
