## MODIFIED Requirements

### Requirement: Embedding cache in Redis
The client SHALL cache each accepted vector in Redis under `iw:emb:v1:{variant}:{content_hash}` with TTL `EMBED_CACHE_TTL_S`. `variant` is derived from `EMBED_MODEL`, `EMBED_DIM` and `EMBED_MAX_CHARS`; `content_hash` is defined by "Embedding cache key". The value SHALL be the float32 vector, encoded as text. A hit SHALL make no HTTP request. Rejected vectors and errors SHALL NOT be cached. This cache SHALL be the only store of document vectors: never Postgres, findings or events.

#### Scenario: Re-scan is free
- **WHEN** the same document is analyzed twice with the same embeddings settings
- **THEN** the stub receives an embeddings request only during the first analysis, and both analyses make the same gate decision

#### Scenario: Model swap misses the cache
- **WHEN** a document is embedded with `EMBED_MODEL=bge-m3`, then with `EMBED_MODEL=multilingual-e5-large`
- **THEN** the second run sends a new request

#### Scenario: Readable through the worker client
- **WHEN** a vector is cached and read back through a Redis client with `decode_responses=True`
- **THEN** it decodes to the same 1024 float32 values

## ADDED Requirements

### Requirement: Embedding cache key
The `content_hash` in the embedding cache key SHALL be the document's stored `ScrapedDocument.content_hash` as the scraper wrote it (ADR 0105); analytics SHALL NOT compute one. A document without a stored `content_hash` SHALL be embedded but not cached.

#### Scenario: No stored hash
- **WHEN** a document without `content_hash` is embedded twice
- **THEN** both calls reach the endpoint and no `iw:emb:v1:*` key is written

#### Scenario: Stored hash is the key
- **WHEN** a document with `content_hash` `abab…` is analyzed
- **THEN** the embedder receives exactly that value as its cache key
