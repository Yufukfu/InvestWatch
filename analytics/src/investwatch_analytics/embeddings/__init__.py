"""Embeddings for the analytics preprocessing (analytics-embeddings; ADR 0313).

`client.EmbedClient` talks to an OpenAI-compatible `/embeddings` endpoint; `embedder.HttpEmbedder` adds the
Redis cache and the circuit breaker and never raises; `build_embedder(settings, redis)` returns `None` when
`EMBED_BASE_URL` is empty.
"""
