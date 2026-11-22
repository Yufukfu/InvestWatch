## MODIFIED Requirements

### Requirement: Response cache in Redis
The judge SHALL cache each fully valid chunk response in Redis under a key derived from `(content_hash, prompt_version, model)` plus module, chunk index, chunk count and the sorted requested rule ids, with TTL `LLM_CACHE_TTL_S`. A cache hit SHALL make no HTTP request and SHALL re-run quote verification. Errors and malformed answers SHALL NOT be cached, and a Redis error SHALL never fail the document.

#### Scenario: Re-scan is free
- **WHEN** the same document is analyzed twice with the same model and catalogue
- **THEN** the stub receives requests only during the first analysis and both findings have the same rule results
- **AND** `content_hash` SHALL be the document's stored value (NFC, `.docs/integration-plan.md` §3), never one analytics computes

#### Scenario: Model swap misses the cache
- **WHEN** a document is analyzed with `LLM_MODEL=gpt-4o-mini`, then with `LLM_MODEL=gemma3:4b`
- **THEN** the second analysis sends new requests

#### Scenario: Question edited
- **WHEN** an `llm.question` in the catalogue changes between two analyses of the same document
- **THEN** the prompt version differs and the second analysis sends new requests
- **AND** `prompt_version` SHALL be derived from a hash of the rendered system prompt

#### Scenario: Malformed answer not cached
- **WHEN** the first analysis gets a malformed answer and the second a valid one
- **THEN** the second analysis sends a request and its verdicts are used

#### Scenario: Redis down
- **WHEN** the Redis client raises a connection error on cache read and write
- **THEN** the LLM is called, the verdicts are used and the document is not failed
- **AND** a Redis error SHALL be treated as a cache miss (or a skipped write) and logged; without a Redis client (CLI) no cache is used

#### Scenario: Document without a stored hash
- **WHEN** a document without `content_hash` is analyzed twice
- **THEN** both analyses send requests and no cache entry is read or written
- **AND** documents without a stored hash SHALL never share a cache key

#### Scenario: The stored hash keys the cache
- **WHEN** two analyses of the same text carry different stored `content_hash` values
- **THEN** each sends its own request and two cache entries exist
