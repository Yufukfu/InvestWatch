## ADDED Requirements

### Requirement: Investment topic gate
After preprocessing and before routing, analytics SHALL decide whether a document is investment-related (`.docs/analytics-plan.md` §2 step 2). The gate SHALL combine two signals:
- **Dictionary hits:** matches of the investment vocabulary in `gate_terms.yaml` against the normalized text, lowercased and with diacritics stripped. Terms are stems or phrases matched on word boundaries, so `zyski`, `zysków` and `zyskow` all match `zysk*`. A registry firm match also counts as a hit.
- **Similarity:** the highest cosine similarity between the document vector and the positive class centroids, when a vector is available. Centroids are the normalized means of the seed phrases in `gate_terms.yaml`, embedded at start-up through the same client and cache.

The gate SHALL drop a document only when the dictionary has no hit **and** either no vector is available or the similarity is below `GATE_SIM_THRESHOLD` (default 0.45). The gate SHALL let every other document through.

Documents with `source_kind` `firm_own` SHALL bypass the gate. `GATE_ENABLED=false` SHALL let every document through.

A dropped document SHALL produce no finding. It SHALL log `document skipped` with reason `off_topic` and the figures `dict_hits`, `similarity` (or null) and `embedder` (model or null), without document text. It SHALL increment `dropped` in the Redis hash `iw:stats:gate`, and a passed document SHALL increment `passed`. A Redis error on the counter SHALL be logged and never raised.

If the centroids cannot be built at start-up (embedder down), the gate SHALL run on the dictionary only and retry the centroids on a later document, after the breaker allows a call.

#### Scenario: Investment post passes on the dictionary
- **WHEN** a `third_party` post says `Zainwestuj w CFD na forex, zyski 20% miesięcznie`
- **THEN** the gate passes it with `dict_hits` at least 3, whether or not an embedder is configured

#### Scenario: Social post without diacritics
- **WHEN** a post says `gielda i kryptowaluty, moje zyski z inwestycji`
- **THEN** the gate passes it on the dictionary

#### Scenario: Off-topic post dropped with a reason
- **WHEN** a `third_party` post about a recipe has no dictionary hit and the stub embedder gives similarity 0.20
- **THEN** no finding is returned, the log line has reason `off_topic`, `dict_hits` 0, `similarity` 0.2 and `embedder` `bge-m3`, and `iw:stats:gate` `dropped` is incremented

#### Scenario: Embedding rescues a post without vocabulary
- **WHEN** a post has no dictionary hit but the stub embedder gives similarity 0.60 to the investment-offer centroid
- **THEN** the gate passes it

#### Scenario: Embedder down, no vocabulary
- **WHEN** the embedder is unavailable and a post has no dictionary hit
- **THEN** the post is dropped with `off_topic`, `similarity` null and `embedder` null

#### Scenario: Embedder down, investment vocabulary
- **WHEN** the embedder is unavailable and a post mentions `obligacje skarbowe`
- **THEN** the gate passes it, and its findings have `model.embedder = null`

#### Scenario: Firm page bypasses the gate
- **WHEN** a `firm_own` document has no dictionary hit
- **THEN** it is not dropped and is routed to M2 as before

#### Scenario: Gate disabled
- **WHEN** `GATE_ENABLED=false` and an off-topic post is analyzed
- **THEN** the gate drops nothing

#### Scenario: Counter on a Redis outage
- **WHEN** the Redis client raises on `HINCRBY iw:stats:gate`
- **THEN** the gate decision and the analysis are unchanged

#### Scenario: Gate terms file invalid
- **WHEN** `gate_terms.yaml` has an empty term list or a centroid class without seed phrases
- **THEN** loading fails at start-up with an error naming the file and the key

### Requirement: Near-duplicate detection and grouping
Analytics SHALL detect near-duplicates among analyzed documents with MinHash (`datasketch`, `NEARDUP_NUM_PERM` permutations, default 128) over word 5-shingles of the normalized, lowercased text, cut to its first `NEARDUP_MAX_CHARS` characters (default 50000). An LSH index in Redis SHALL hold `NEARDUP_BANDS` bands (default 32, of 4 rows each).

A candidate found in any band SHALL count as a near-duplicate only if its estimated Jaccard similarity, computed from the stored signatures, is at least `NEARDUP_THRESHOLD` (default 0.8). The document's own id SHALL never match itself, so a redelivery is not reported as its own duplicate. Texts with fewer than 5 words (no shingle) SHALL skip near-dup detection.

A near-duplicate SHALL still be analyzed and SHALL still get its own findings. Its group SHALL be recorded:
- `iw:neardup:v1:doc:{document_id}` maps the document to its group id, which is the `document_id` of the earliest member;
- `iw:neardup:v1:group:{group_id}` is the set of member ids;
- the band buckets and signatures carry TTL `NEARDUP_TTL_S` (default 30 days).

The group SHALL be logged (`neardup`, with group id, best similarity and member count, without text). Each finding of a document with at least one other member SHALL carry one Polish sentence in its `summary` naming the number of near-identical analyzed materials. A Redis error SHALL skip detection for that document, be logged and never be raised. Without a near-dup index (CLI), detection is off. Exact duplicates by `content_hash` within one source remain the scraper's concern (document-ingest).

#### Scenario: Repost with a changed handle
- **WHEN** two `third_party` posts share the same 300-word text except for the author handle and one emoji
- **THEN** the second post joins the group of the first, both are analyzed, and the second's findings' summary says one near-identical material was found

#### Scenario: Different texts
- **WHEN** two posts about different offers share fewer than half of their shingles
- **THEN** neither is recorded as a near-duplicate of the other

#### Scenario: Changed page version
- **WHEN** a firm page is re-scraped with one paragraph changed, giving a new `document_id`
- **THEN** both documents are in one group and each has its own M2 finding (the `Finding` contract is unchanged)

#### Scenario: Redelivery is not its own duplicate
- **WHEN** the same document id is analyzed twice
- **THEN** its group has one member and the summary has no near-dup sentence

#### Scenario: Too short
- **WHEN** the text has four words
- **THEN** no MinHash is computed and no Redis key is written for it

#### Scenario: Index down
- **WHEN** the Redis client raises a connection error during the near-dup lookup
- **THEN** the document is analyzed, its summary has no near-dup sentence, and the log reason is `neardup_unavailable`

#### Scenario: Works without embeddings
- **WHEN** `EMBED_BASE_URL` is unset and a repost is analyzed
- **THEN** it is still grouped with its original

### Requirement: Embedder recorded on findings
Every finding SHALL set `model.embedder` to `EMBED_MODEL` when a validated document vector, from the endpoint or the cache, was obtained for that document. It SHALL be `null` otherwise: embeddings disabled, unavailable, malformed, or breaker-open. Findings SHALL stay valid against `contracts/schemas/finding.schema.json` v1, and no contract field SHALL be added.

#### Scenario: Embedder used
- **WHEN** a passing post is analyzed with a stub embedder returning a valid vector and `EMBED_MODEL=bge-m3`
- **THEN** its findings have `model.embedder` `bge-m3` and validate with `contracts/validate.py finding`

#### Scenario: Cached vector counts as used
- **WHEN** the vector comes from the Redis cache and no request is made
- **THEN** `model.embedder` is `bge-m3`

#### Scenario: Embedder failed
- **WHEN** the stub returns a wrong-size vector
- **THEN** the findings have `model.embedder = null`
