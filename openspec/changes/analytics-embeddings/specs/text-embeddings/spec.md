## ADDED Requirements

### Requirement: Env-only embeddings configuration
Analytics SHALL configure embeddings only from environment variables: `EMBED_BASE_URL`, `EMBED_MODEL` (default `bge-m3`), `EMBED_API_KEY`, `EMBED_DIM` (default 1024), `EMBED_TIMEOUT_S` (default 5), `EMBED_MAX_CHARS` (default 4000), `EMBED_CACHE_TTL_S` (default 604800), `EMBED_BREAKER_FAILURES` (default 3) and `EMBED_BREAKER_COOLDOWN_S` (default 60). With `EMBED_BASE_URL` empty or unset, embeddings SHALL be disabled and analysis SHALL continue without them. A set `EMBED_BASE_URL` with an empty `EMBED_MODEL`, or a non-numeric or non-positive limit, SHALL be a configuration error that names the variable, and the worker SHALL exit with code 2. The API key SHALL never appear in logs or error messages. The documented defaults in `analytics/.env.example` SHALL point to the local `ollama` service (`http://ollama:11434/v1`, `bge-m3`), never to a paid hosted API.

#### Scenario: Embeddings disabled by default
- **WHEN** `EMBED_BASE_URL` is unset and a document is analyzed
- **THEN** no embeddings request is made and every finding has `model.embedder = null`

#### Scenario: Model missing
- **WHEN** `EMBED_BASE_URL` is set and `EMBED_MODEL` is an empty string
- **THEN** the worker does not start, exits with code 2, and the error names `EMBED_MODEL`

#### Scenario: Bad number
- **WHEN** `EMBED_DIM=abc` or `EMBED_TIMEOUT_S=0`
- **THEN** startup fails with an error naming that variable

#### Scenario: Key never logged
- **WHEN** a request with `EMBED_API_KEY=sk-emb-123` fails with HTTP 401
- **THEN** no log line contains `sk-emb-123`

### Requirement: OpenAI-compatible embeddings request
The client SHALL send `POST {EMBED_BASE_URL}/embeddings` with the JSON body `{"model": EMBED_MODEL, "input": [<text>]}`, using no provider SDK and no header other than `Authorization: Bearer <key>` when a key is set. The input SHALL be the normalized text cut to its first `EMBED_MAX_CHARS` characters. The client SHALL read `data[0].embedding`. It SHALL NOT log the request or response body. The same code SHALL work against Ollama's `/v1` endpoint and any OpenAI-compatible embeddings server.

#### Scenario: Request shape
- **WHEN** a document is embedded against the local stub server
- **THEN** the stub receives one request on `/v1/embeddings` whose body has the configured `model` and an `input` list of one string of at most `EMBED_MAX_CHARS` characters

#### Scenario: Long text is cut
- **WHEN** the normalized text has 20000 characters and `EMBED_MAX_CHARS=4000`
- **THEN** the input sent is exactly its first 4000 characters

#### Scenario: No key configured
- **WHEN** `EMBED_API_KEY` is empty
- **THEN** the request carries no `Authorization` header

#### Scenario: Bodies stay out of the logs
- **WHEN** a call succeeds on a document containing `Zarabiaj 18% rocznie`
- **THEN** no log line contains that text or any vector value

### Requirement: Vector validation
A vector SHALL be accepted only if it is a list of exactly `EMBED_DIM` finite numbers with a non-zero norm. Anything else SHALL be treated as malformed: a missing `data`, an empty list, a wrong length, `NaN` or infinite values, non-numbers, or an all-zero vector. Accepted vectors SHALL be L2-normalized and stored as float32.

#### Scenario: Wrong vector size
- **WHEN** the stub answers a 768-element vector and `EMBED_DIM=1024`
- **THEN** the vector is rejected, the log reason is `embed_malformed` naming the received and expected size, and the document is analyzed without an embedding

#### Scenario: NaN in the vector
- **WHEN** the stub answers a 1024-element vector containing `NaN`
- **THEN** the vector is rejected as malformed

#### Scenario: Zero vector
- **WHEN** the stub answers 1024 zeros
- **THEN** the vector is rejected as malformed

#### Scenario: Not embeddings JSON
- **WHEN** the stub answers HTTP 200 with `{"error": "model not found"}` or a body that is not JSON
- **THEN** the vector is rejected as malformed

### Requirement: Degrade without embeddings
A connection error, a timeout after `EMBED_TIMEOUT_S`, an HTTP status of 404, 429, 401, 403 or 5xx, or a malformed answer SHALL NOT fail the document. The pipeline SHALL continue with no vector: the gate SHALL use the dictionary only, and every finding of that document SHALL have `model.embedder = null`. A log line SHALL name the reason (`embed_unavailable`, `embed_timeout`, `embed_malformed`) and contain no document text. Empty normalized text SHALL never be sent to the embedder.

#### Scenario: Embedder down
- **WHEN** `EMBED_BASE_URL` points to a closed port and an investment post is analyzed
- **THEN** the analysis completes with `model.embedder = null`, the gate decision comes from the dictionary, and the log reason is `embed_unavailable`

#### Scenario: Embedder slow
- **WHEN** the stub sleeps longer than `EMBED_TIMEOUT_S` before answering
- **THEN** the call is abandoned within the timeout plus one second, the log reason is `embed_timeout`, and the document is analyzed without an embedding

#### Scenario: Model not pulled
- **WHEN** the stub answers HTTP 404 (Ollama without `bge-m3` pulled)
- **THEN** the document is analyzed without an embedding and the log reason is `embed_unavailable`

#### Scenario: Empty text
- **WHEN** `text` is whitespace only
- **THEN** no embeddings request is made and the document is skipped with reason `empty_text`, as before

### Requirement: Embeddings circuit breaker
After `EMBED_BREAKER_FAILURES` consecutive unavailable outcomes (connection error, timeout, 404, 429, 401, 403, 5xx), the client SHALL stop calling for `EMBED_BREAKER_COOLDOWN_S` and return no vector at once. After the cooldown it SHALL try one call: success closes the breaker, and failure reopens it. Malformed answers SHALL NOT count toward the breaker. The breaker is in memory, per process.

#### Scenario: Breaker opens
- **WHEN** three consecutive embeddings calls fail with connection refused and a fourth document is analyzed within the cooldown
- **THEN** the fourth document makes no embeddings request and is analyzed without an embedding

#### Scenario: Breaker half-open
- **WHEN** the cooldown has passed and the next call succeeds
- **THEN** later documents call the endpoint again

### Requirement: Embedding cache in Redis
The client SHALL cache each accepted vector in Redis under `iw:emb:v1:{variant}:{content_hash}`, with TTL `EMBED_CACHE_TTL_S`. `variant` is derived from `EMBED_MODEL`, `EMBED_DIM` and `EMBED_MAX_CHARS`. `content_hash` SHALL be analytics' own preprocessing hash. The value SHALL be the float32 vector, encoded so that it can be read by a client with `decode_responses=True`. A cache hit SHALL make no HTTP request. A cached value of the wrong length SHALL be treated as a miss and overwritten. Rejected vectors and errors SHALL NOT be cached. A Redis error SHALL be treated as a miss or a skipped write, logged and never raised. Without a Redis client (CLI), no cache is used. This TTL-bound cache SHALL be the only place where a document vector is stored: vectors SHALL NOT be written to Postgres, to findings or to events.

#### Scenario: Re-scan is free
- **WHEN** the same document is analyzed twice with the same embeddings settings
- **THEN** the stub receives an embeddings request only during the first analysis, and both analyses make the same gate decision

#### Scenario: Model swap misses the cache
- **WHEN** a document is embedded with `EMBED_MODEL=bge-m3`, then with `EMBED_MODEL=multilingual-e5-large`
- **THEN** the second run sends a new request

#### Scenario: Cache down
- **WHEN** the Redis client raises a connection error on both cache read and write
- **THEN** the embedder is called, the vector is used, and the document is not failed

#### Scenario: Corrupt cache entry
- **WHEN** the cached value under the document's key decodes to 512 floats with `EMBED_DIM=1024`
- **THEN** it is treated as a miss, a request is sent, and the entry is overwritten

### Requirement: Tests never call a real model
Embeddings tests SHALL use a stub OpenAI-compatible server on `127.0.0.1` with a scripted queue of answers (a valid vector, a wrong size, `NaN`, a zero vector, non-JSON, HTTP 404, 429, 500 and 401, a sleep past the timeout, a closed connection), or a fake embedder. A test guard SHALL fail any test that builds an embedder whose base URL is not loopback.

#### Scenario: Guard
- **WHEN** a test builds an embedder with `EMBED_BASE_URL=http://ollama:11434/v1`
- **THEN** the test fails with a message naming the guard
