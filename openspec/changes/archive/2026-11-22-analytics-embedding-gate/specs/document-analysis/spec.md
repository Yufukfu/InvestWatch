## ADDED Requirements

### Requirement: Embedding rescue in the topic gate
When a gated (`third_party` or `unknown`) document has no dictionary hit, its normalized text has at least `GATE_EMBED_MIN_CHARS` characters (default 40), and the gate has an embedder and built centroids, analytics SHALL embed the document and compute `margin = max cos(vector, on-topic class centroid) − cos(vector, off_topic centroid)`. The centroids are the normalized means of the seed lines in `gate_terms.yaml` `centroids`, where `off_topic` is a reserved class. The gate SHALL pass the document with reason `embedding` when `margin ≥ GATE_EMBED_MIN_MARGIN`, and otherwise drop it with `off_topic`. Embeddings SHALL never be consulted for a document that has a dictionary hit, so they can never drop a document the dictionary passes. The document's vector SHALL be the one recorded in `model.embedder`, so it is not embedded a second time.

#### Scenario: Vocabulary-free offer rescued
- **WHEN** a `third_party` post has no dictionary hit, is longer than 40 characters, and its vector is closer to an on-topic centroid than to `off_topic` by at least the margin
- **THEN** the gate passes it with reason `embedding` and path `embedding`, and it is routed to M1/M3 as usual

#### Scenario: Off-topic text stays dropped
- **WHEN** a `third_party` post about a football match has no dictionary hit and its margin is below `GATE_EMBED_MIN_MARGIN`
- **THEN** it is dropped with reason `off_topic` and path `embedding`

#### Scenario: Dictionary pass is never re-judged
- **WHEN** a post has a dictionary hit and the embedder would place it next to the `off_topic` centroid
- **THEN** the gate passes it with path `dictionary`, and the gate does not call the embedder for the decision

#### Scenario: Short text is not embedded for the gate
- **WHEN** a post with no dictionary hit has fewer than `GATE_EMBED_MIN_CHARS` characters
- **THEN** it is dropped with path `dictionary`, and the embedder is not called

#### Scenario: firm_own is unaffected
- **WHEN** a `firm_own` page has no dictionary hit
- **THEN** it bypasses the gate as before, whatever the embedder says

#### Scenario: Gold positives keep passing
- **WHEN** every gold-set document labelled positive for M1 or M3 runs through the gate with an embedder that places every text next to `off_topic`
- **THEN** none of them is dropped

#### Scenario: Seed classes invalid
- **WHEN** `gate_terms.yaml` has `centroids` without an `off_topic` class, or with `off_topic` only
- **THEN** loading fails at start-up with an error naming the file and `centroids`

#### Scenario: Margin from env
- **WHEN** `GATE_EMBED_MIN_MARGIN` is not a number in [0, 1], or `GATE_EMBED_MIN_CHARS` is not a positive integer
- **THEN** start-up fails with an error naming the variable

### Requirement: Embedding gate degrades to the dictionary
The centroids SHALL be built outside any message: once at start-up, then between messages at most once per `EMBED_BREAKER_COOLDOWN_S` while none exist. Each seed is embedded through the same embedder and cache (`iw:emb:v1:*`, keyed on the seed's content hash). With no embedder configured, the breaker open, a failed document vector, or no centroids, the gate SHALL decide on the dictionary alone with path `dictionary_only_fallback`. It SHALL never raise or fail the document, and it SHALL make at most the one embedding call per document that the pipeline already makes. The reason SHALL be logged once per change of reason, not once per document.

#### Scenario: Default stack without an embedder
- **WHEN** `EMBED_BASE_URL` is empty and a `third_party` post without a dictionary hit is analyzed
- **THEN** it is dropped with `off_topic` and path `dictionary_only_fallback`, and `embedding gate off` is logged once at start-up, not per document

#### Scenario: Embedder down while centroids exist
- **WHEN** centroids are built, the embedder then returns `embed_unavailable` for a no-hit post, and a second no-hit post follows
- **THEN** both are dropped with path `dictionary_only_fallback`, and `embedding gate degraded` with reason `embed_unavailable` is logged once

#### Scenario: Centroids built after an outage
- **WHEN** the embedder is down at start-up and comes back later
- **THEN** the worker builds the centroids between messages, logs `embedding gate restored`, and later no-hit posts take path `embedding`

#### Scenario: Centroids never built inside a message
- **WHEN** a no-hit post is analyzed before any centroids exist
- **THEN** the pipeline makes no seed embedding call for it and uses path `dictionary_only_fallback`

#### Scenario: Restart reuses cached seed vectors
- **WHEN** a worker restarts with the Redis embedding cache intact
- **THEN** building the centroids makes no embeddings request

## MODIFIED Requirements

### Requirement: Dropped documents are logged
A document dropped by the gate SHALL produce no finding. It SHALL log `document skipped` with reason `off_topic` and the figures `dict_hits`, `gate_path` (`dictionary`, `embedding` or `dictionary_only_fallback`), `similarity` (the highest cosine to an on-topic centroid, or null when no embedding decided), `margin` (or null) and `embedder` (the model, or null), without document text. Its `documents` row SHALL stay untouched, so it can be re-analyzed.

#### Scenario: Off-topic post dropped with a reason
- **WHEN** a `third_party` post about a recipe has no dictionary hit and no embedder is configured
- **THEN** no finding is returned, and the log line has reason `off_topic`, `dict_hits` 0, `gate_path` `dictionary_only_fallback` and `similarity` null

#### Scenario: Embedding drop logged with its figures
- **WHEN** a no-hit post is dropped on the embedding path
- **THEN** the log line has `gate_path` `embedding` and numeric `similarity` and `margin`

#### Scenario: No text in the log
- **WHEN** a post containing `Przepis na sernik babci` is dropped
- **THEN** no log line contains that text

### Requirement: Gate counters
The gate SHALL increment `passed`, `dropped` or `bypassed` in the Redis hash `iw:stats:gate` for each decision when a Redis client is available. For a gated decision it SHALL also increment `path_dictionary`, `path_embedding` or `path_dictionary_only_fallback`, and `rescued` when the embedding passed the document. A Redis error on the counter SHALL be logged and never raised.

#### Scenario: Drop counted
- **WHEN** an off-topic post is dropped in the worker without an embedder
- **THEN** `iw:stats:gate` `dropped` and `path_dictionary_only_fallback` are each incremented by 1

#### Scenario: Rescue counted
- **WHEN** a no-hit post is passed by the embedding in the worker
- **THEN** `passed`, `path_embedding` and `rescued` are each incremented by 1

#### Scenario: Counter on a Redis outage
- **WHEN** the Redis client raises on `HINCRBY iw:stats:gate`
- **THEN** the gate decision and the analysis are unchanged
