# Design

## Context

Stage 3 of analytics. Read at `analytics/analytics-llm-p0` `5b4a547`, which already contains the merged `analytics-worker` code:

- `preprocessing.py`: NFKC normalization, `content_hash` = sha256 of the normalized text, a pl/en guess, and sentences with spans into the original. No near-dup step.
- `pipeline.py`: `analyze(doc, *, registry, catalogue, now, new_id)`, pure. Empty text is skipped (`empty_text`), then routing (`module_not_implemented` for non-`firm_own`), then M2. No topic gate.
- The `analytics-llm-p0` design (planned, groups 5-12 not applied yet):
  - an `httpx` client with no SDK, configured by env, with the error taxonomy `LlmUnavailable` / `LlmMalformed`;
  - a breaker per process;
  - a Redis cache keyed on analytics' own `content_hash`;
  - a stub `ThreadingHTTPServer` and a loopback guard in tests;
  - `analyze(..., judge=None)` with injected I/O, and `build_judge(settings, redis)` that returns `None` when disabled.

  This change mirrors all of that.
- The worker builds the stream Redis client with `decode_responses=True` (`worker.py:262-266`), so cached vectors are stored as base64 text, not raw bytes.
- `finding.schema.json` v1 already has `model.embedder` (string or null). `contracts/mocks/findings.json` shows `embedder: bge-m3`.
- Infra: the optional `ollama` service (profile `llm`) on the `data` network at `http://ollama:11434/v1`, which pulls only `gemma3:4b` (`shared-infrastructure` spec).

Sources:
- `doc/Opis Wyzwania HackNation UKNF 19.11.pdf` p.2: tokens, embeddings, deduplication. §5: open-source, no paid APIs.
- `.docs/analytics-plan.md` §1.5 (`bge-m3` or `multilingual-e5`), §2 steps 1-2, §7 (embeddings for the gate, near-dup and grouping).
- ADR 0304, issues #31, #32 and #33, and the URL-level grouping follow-up from Kacper's #26 review.

## Goals / Non-Goals

**Goals:**
- The three preprocessing items the challenge names (embeddings, a topic gate, near-dup), visible in findings (`model.embedder`), in logs and in Redis.
- Nothing here can stop a document: every failure path ends in "dictionary-only gate, no vector, no near-dup sentence".
- The gate is biased to recall: it drops only content with no investment signal at all.
- No contract change. Fully offline tests.

**Non-Goals:**
- A vector database, ANN search or similar-ad clustering for the dashboard.
- API or UI for near-dup groups.
- Redefining `content_hash` (#31).
- Using embeddings in M1-M3 rules.

## Decisions

### 1. Model and serving: `bge-m3` on local Ollama, through `/v1/embeddings` (ADR 0313)

`bge-m3` has open weights under the MIT licence, is multilingual (Polish included), outputs 1024 dimensions, takes up to 8192 tokens of input, and is in the Ollama library as `bge-m3`. `multilingual-e5-large` was the plan's alternative. It needs `query:` / `passage:` prefixes, takes 512 tokens, and is not in the official Ollama library, so it would need a second server or a custom import.

The client speaks the OpenAI-compatible `POST /embeddings`, which Ollama serves under `/v1`, not Ollama's native `/api/embed`. The swap rule is the same as ADR 0304: any OpenAI-compatible embeddings server (Ollama, vLLM, TEI with its OpenAI route, llama.cpp server) works by env only.

The difference from the LLM: **no hosted default.** The mentor exception in ADR 0304 covers the LLM, not embeddings. A hosted embeddings API is a paid API, which §5 of the PDF excludes. Embeddings are cheap to run locally, so the documented configuration is local only. A plain `docker compose up` (without the `llm` profile) therefore runs with embeddings off, and that is a supported state.

The embeddings env set is separate from the LLM one (`EMBED_*`, not `LLM_*`), because the LLM is hosted by default while embeddings are local. Two base URLs are the honest shape.

### 2. Client: a mirror of the LLM client

- `embeddings/client.py`:
  - `httpx` (sync), connect timeout 3 s, read timeout `EMBED_TIMEOUT_S` (5);
  - body `{"model", "input": [text]}`, read `data[0].embedding`;
  - errors map to `EmbedUnavailable` (connection, DNS, timeout, 404, 429, 401, 403, 5xx) or `EmbedMalformed` (HTTP 200 but not the expected JSON, or a vector that fails validation);
  - 404 is unavailable here (unlike the LLM), because Ollama answers 404 for a model that is not pulled, which is the most likely demo failure.
- **Validation:** length == `EMBED_DIM`, all values finite, norm > 0. The vector is then L2-normalized into a `numpy.float32` array, so cosine is a dot product.
- **Breaker:** the same semantics as `analytics-llm-p0` §6. If that change's breaker is generic (a `Breaker(failures, cooldown, clock)` class), it is reused. Otherwise a small copy lives in `embeddings/breaker.py`, and the duplication is noted in `follow-ups.md` (task 3.1 checks which).
- **Input:** `pre.normalized[:EMBED_MAX_CHARS]`, 4000 by default, about 1.3k Polish tokens. The topic is decided by the headline and the lead. A short input keeps `bge-m3` fast on CPU, and it does not depend on the server's context length (#32). Empty text is never sent (the pipeline skips it earlier).
- **No document budget.** There is one call per document, and the 5 s timeout plus the breaker bound it. The 5 s are added to the LLM's `LLM_DOC_BUDGET_S` worst case. Config validation requires `(LLM_DOC_BUDGET_S + EMBED_TIMEOUT_S) * 1000 < CLAIM_MIN_IDLE_MS`, the same XAUTOCLAIM reason as ADR 0310.
- **Logs:** the host, the model, the status, the latency and the error class. Never the text, the vector or the key.
- **Defaults:** `EMBED_MODEL=bge-m3`, `EMBED_DIM=1024`, `EMBED_TIMEOUT_S=5`, `EMBED_MAX_CHARS=4000`, `EMBED_CACHE_TTL_S=604800` (7 days), `EMBED_BREAKER_FAILURES=3`, `EMBED_BREAKER_COOLDOWN_S=60`. Near-dup: `NEARDUP_NUM_PERM=128`, `NEARDUP_BANDS=32`, `NEARDUP_THRESHOLD=0.8`, `NEARDUP_MAX_CHARS=50000`, `NEARDUP_TTL_S=2592000` (30 days). Gate: `GATE_ENABLED=true`, `GATE_SIM_THRESHOLD=0.45`.

### 3. Cache

- **Key:** `iw:emb:v1:{variant}:{content_hash}`, where `variant = sha256(EMBED_MODEL|EMBED_DIM|EMBED_MAX_CHARS)[:12]`. The brief asks for `content_hash` + model. `EMBED_MAX_CHARS` changes the input and so the vector, which is why it is part of the variant.
- **Value:** base64 of the float32 bytes (4 KB → about 5.5 KB of text), readable through the worker's `decode_responses=True` client. A separate cache client with a 1 s socket timeout is used, like the LLM cache.
- **TTL:** 7 days.
- A decoded value of the wrong length is a miss and is overwritten. A Redis error is a miss or a skipped write, logged and never raised.
- **Seed phrases for the centroids** are cached the same way (their `content_hash` is computed with the same `preprocessing.content_hash`), so a worker restart does not re-embed them.
- **#31:** both write and read use analytics' own NFKC hash, so the keys are consistent whatever the scraper does. If #31 later makes analytics read `ScrapedDocument.content_hash`, every key changes once. That is a cold cache, not a bug.

### 4. Topic gate (ADR 0314)

`gate.py` and `gate_terms.yaml`, data rather than code, in the style of `m2_rules.yaml`:

```yaml
version: 1
terms:            # stems (trailing *) or phrases, diacritic-insensitive, word-boundary
  - inwest*       # inwestycja, inwestuj; zainwestuj via the prefix list below
  - zysk*
  - "stopa zwrotu"
  - akcj*
  - CFD
  - forex
  - krypto*
  - bitcoin*
  - obligacj*
  - ETF
  - portfel*
  - makler*
  - giel*         # written without diacritics; the matcher strips them from the text too
  - dywidend*
  - fundusz*
  - lokat*
  - sygnal*
  - dzwigni*
  - trad*
  - pips*
  # … plus English: invest*, profit*, return*, broker*, stock*, crypto*, signal*
prefixes: [za, po]   # zainwestuj, pomnóż… matched as prefix + stem
centroids:
  investment_offer:  [ "Zainwestuj i zarabiaj co miesiąc", "Gwarantowany zysk z inwestycji", … ]
  finfluencer:       [ "Moje portfolio i sygnały na dziś", … ]
  advisory_service:  [ "Pomogę Ci pomnożyć oszczędności, napisz na priv", … ]
```

Matching runs on `strip_diacritics(pre.normalized.lower())`, over the first 200k characters only. The topic shows in the headline and lead, and the cap bounds the regex cost on hostile input. Without the stretch similarity rescue, a real investment post that uses none of the vocabulary is dropped (logged as `off_topic`). That is the known cost of the dictionary-only gate. Social posts often drop diacritics, and the gate errs toward a match. A registry firm match (`registry.match`) counts as one hit.

**Decision rule.** The gate drops only if `dict_hits == 0 and (vector is None or max_sim < GATE_SIM_THRESHOLD)`.
- The embedding can only rescue a document. It never drops one the dictionary kept. That is the "low threshold, let content through" rule from plan §2.
- With no embedder, the gate is the dictionary alone.

**Similarity rescue is a stretch item** (task group 5, the first cut). Without it, the gate is dictionary-only and `similarity` is null in the log. The embeddings still fill `model.embedder` and the cache, which meets the "Reprezentacja wektorowa … embeddingów" requirement.

`GATE_SIM_THRESHOLD` is 0.45 by default. `bge-m3` cosine scores between unrelated Polish texts usually sit around 0.3-0.4, so 0.45 lets near-topic text through. That number is unmeasured, and it is calibrated on the gold set (plan §8) during Integration #3. The env makes it adjustable without a release.

**Centroids** are the normalized means of each class's seed vectors. They are built lazily on the first document when the embedder is up, and rebuilt on the first successful call after an outage. With no centroids there is no similarity, so the gate uses the dictionary only for that document. No negative class: a "non-financial" centroid would make the gate drop by comparison, which is the opposite of the recall bias.

**`firm_own` bypasses the gate.** M2 covers only material "publikowanych bezpośrednio przez" firms and must check every page of one (a "kontakt" page still needs R1). The scraper only labels `firm_own` for sources UKNF configured. The gate applies to `third_party` and `unknown`, and documents that pass flow to routing (M1/M3) unchanged. Damian confirmed this.

**Not a silent loss.** Each drop is one INFO log line, `document skipped` with reason `off_topic`, `dict_hits`, `similarity`, `embedder` and `document_id`. The Redis hash `iw:stats:gate` counts `passed`, `dropped` and `bypassed`. The worker acks the message as it does for `empty_text`, and the `documents` row stays in Postgres, so a drop can be re-analyzed after a threshold change. `GATE_ENABLED=false` turns the gate off for a demo or for an evaluation run.

The rejected option of an LLM gate costs one call per document for a yes/no that a dictionary handles. Plan §1 says rules before the LLM.

### 5. Near-duplicates (ADR 0314)

**Technique.** `datasketch.MinHash`, 128 permutations, over word 5-shingles of `strip_diacritics(normalized.lower())`, cut to 50k characters (bounded cost: about 8k shingles, one numpy pass). We keep our own LSH in Redis: 32 bands of 4 rows, bucket key `iw:neardup:v1:b:{band}:{sha1(band rows)[:16]}` → a set of document ids. The signature (128 × little-endian uint32, base64) and the url (capped at 2048 characters) are stored in the hash `iw:neardup:v1:meta:{document_id}`. Buckets are read with `SRANDMEMBER` (at most 64 ids) and stop growing at 256 ids, so a flood of identical spam costs O(1) per copy and its full buckets expire.
- Candidates from any band are verified by the Jaccard estimate (the share of equal signature values) ≥ 0.8.
- With 32×4 bands, a pair at Jaccard 0.8 is caught with probability 1-(1-0.8⁴)³² ≈ 0.99999.
- Candidate verification removes the extra false candidates the low band threshold lets in.

Why not `datasketch.MinHashLSH` with its Redis storage: it opens its own connection from host and port config, so it cannot use the worker's client or `fakeredis` in tests, and its key layout is opaque. Banding is about 30 lines.

Why not SimHash: it is weaker on short posts and on partial overlap (a repost with an added paragraph). Jaccard over shingles reads better in the explanation.

Why not embedding similarity for dedup: it needs a vector index (Redis 8 without Stack has none, and pgvector would need Damian's `api/` schema). It also does not work with the embedder off, while near-dup has to work in a plain `docker compose up`.

**What a near-dup means.** The `Finding` contract is frozen, `findings` are unique per `(document_id, module)`, and every publication is separate evidence for the supervisor. So a near-dup is **not dropped and not merged**:
1. The group id is the `document_id` of the earliest member (the first candidate's group, or the document itself).
   - `iw:neardup:v1:doc:{id}` → group id;
   - `SADD iw:neardup:v1:group:{gid} id`;
   - all keys with TTL `NEARDUP_TTL_S`, 30 days.
2. The member's `url` is stored in `iw:neardup:v1:meta:{id}` (a hash with `sig` and `url`).
3. Log `neardup` with the group id, the best Jaccard and the member count.
4. Each finding of a non-original member gets one Polish sentence in its `summary`: "Treść niemal identyczna z materiałem {original_url} (łącznie {n} podobnych materiałów)." Plural forms are picked by `n`. The finding's own `url` stays the near-dup's URL, because M1 needs "dokładną lokalizację (URL)". The summary is free text, so the contract is unchanged.
5. **No repeat alert** (Damian, answer 1). The worker passes each saved finding's group id to the publisher. Before sending `finding.high_risk`, the publisher runs `SET iw:neardup:v1:alerted:{gid}:{module} 1 NX EX NEARDUP_TTL_S`:
   - success → send;
   - the key already exists → skip, and log `high_risk_suppressed` with reason `neardup`;
   - a Redis error → send (fail open).

   `finding.created` is always sent. The claim is per module and is taken only when an alert is about to be sent, so a low-score original does not block a high-score copy. The claim comes before the PUBLISH, so a PUBLISH failure right after it loses that group's alert. This matches the existing at-most-once rule ("Publishing failure does not lose findings"). The change sits in `events.py` (`publish_findings(saved, groups=None)`) and is a MODIFIED requirement in `finding-events`. Known cost: one scam template that names different impersonated firms forms one group, so only the first firm's finding alerts. The later ones are still stored and announced with `finding.created`.

Groups are not merged transitively. A document that matches two groups joins the one with the higher Jaccard. That keeps the writes O(1), and it is an accepted error.

**Order and idempotency.** The lookup excludes the document's own id, so a redelivery after a crash between the Redis write and the DB commit does not make the document its own duplicate. The writes are SADD and SET, which are idempotent. Near-dup runs after the gate, so off-topic text never enters the index, and before routing.

**Bridge to the URL-level grouping follow-up and #33.** The group map is the data an API endpoint or UI grouping needs ("this finding has 4 near-identical copies"). Exposing it is a follow-up: either the API reads `iw:neardup:v1:doc:*`, or a nullable `group_id` goes into `findings.payload` in a later contract version. Neither is in this change.

### 6. Wiring

- `analyze(doc, *, registry, catalogue, now, new_id, judge=None, embedder=None, neardup=None)`. The order is:
  1. preprocess, and skip on `empty_text`;
  2. embed if an embedder is set (any `source_kind`, so `model.embedder` is honest and the vector is cached);
  3. gate, unless `firm_own` bypasses it;
  4. near-dup, if an index is set;
  5. route;
  6. modules;
  7. set `model.embedder` and append the near-dup sentence.

  `embedder` is an `Embedder` protocol (`embed(text, content_hash) -> EmbedOutcome(vector | None, model, status)`). `neardup` is a `NearDupIndex` protocol (`observe(document_id, normalized_text, url) -> NearDupResult | None`).
- The finding builders (M2 now, M1/M3 when `analytics-m1-m3` lands) get the embedder model and the near-dup result through `Context`. That is one additive field, `ctx.pre_extras`, so no builder signature changes.
- `embeddings.build_embedder(settings, redis=None)` returns `None` when disabled. `neardup.build_index(settings, redis)` returns `None` without Redis.
- **Worker:** it builds both at start, logs `embed_mode: local|remote|disabled`, and passes them to `analyze`.
- **CLI:** it builds the embedder (no cache) when `EMBED_BASE_URL` is set. `--no-embed` forces it off. No near-dup index. `--no-gate` is not added, because `GATE_ENABLED=false` covers it.
- **Compose:** `analytics/compose.yaml` passes `EMBED_*`, `GATE_*` and `NEARDUP_*` from the root `.env`. `ollama` is on `data`, which the worker already joins. No new network.
- **Config errors** use the existing `ConfigError` with exit 2.

### 7. Tests never call a real model

- **`stub_embed`:** a `ThreadingHTTPServer` on `127.0.0.1:0` serving `/v1/embeddings` from a scripted queue:
  - deterministic valid vectors: a seeded hash of the text, so that "similar" seeds give a high cosine;
  - a fixed vector per test when needed;
  - a wrong size, `NaN`, zeros, non-JSON, `{"error":…}`;
  - HTTP 404, 429, 401 and 500;
  - a sleep past the timeout, and a closed connection.

  It records the requests. If `analytics-llm-p0`'s `stub_llm` fixture is generic over the route, it is extended rather than copied.
- **`FakeEmbedder`** returns canned vectors for gate and pipeline tests. **`fakeredis`** backs the cache, the gate counter and the near-dup index. A Redis that raises on demand covers the "cache down" and "index down" scenarios.
- **Guard:** a conftest guard fails any test that builds an embedder with a non-loopback base URL.

### 8. Dependencies

- `datasketch==2.0.0` (MIT; requires `numpy>=1.11` and `scipy>=1.0.0`, read from PyPI metadata on 2026-11-21). `numpy` is also used for the vectors. `scipy` is pulled only by `datasketch` (the LSH parameter optimizer, which we don't use). It adds about 40 MB to the image.
  - The alternative is about 30 lines of our own numpy MinHash, which drops `scipy`. It is kept as a cut option (cut plan 4).
  - The plan names `datasketch`, and the jury reviews the libraries.
- `pip-audit` runs on the new pins.

## Risks / Trade-offs

- **The gate drops a real investment post** (false negative). → The dictionary is broad and diacritic-free, the embedding can only rescue, and `firm_own` bypasses the gate. Every drop is logged with its figures, the `documents` row stays for a re-run, and `GATE_ENABLED=false` is an instant kill switch. The gold set gets off-topic negatives and vocabulary-free positives (task 4.1).
- **`GATE_SIM_THRESHOLD` is not measured.** → Env, with calibration on the gold set. The default errs toward passing.
- **`bge-m3` on CPU is slow or evicts Gemma.** → 4000-character input, a 5 s timeout, the breaker and the cache, plus infra ask 2 (`OLLAMA_MAX_LOADED_MODELS=2`). With the hosted LLM default, only `bge-m3` lives in Ollama anyway.
- **The infra asks are not done by the demo.** → Embeddings off is a valid state: the dictionary gate, near-dup and `model.embedder = null` still work. The README says how to pull `bge-m3` by hand.
- **The near-dup index grows without bound.** → A 30-day TTL. About 4-5 KB per document: unrelated documents rarely share a bucket, so each creates about 32 small set keys, plus the meta hash, the doc key and the group key. That is about 4-5 GB at 1M documents in 30 days, and negligible at hackathon scale. A new member refreshes the TTL of the group and of its original, so the original's URL lives as long as the group.
- **Shared files with `analytics-llm-p0` and `analytics-m1-m3`.** → This change lands after llm-p0 and rebases on `main`. Its spec deltas are ADDED requirements only, so archiving does not touch the requirements the other two modify.
- **Behaviour change for `third_party`.** With M1/M3 live, off-topic posts no longer produce findings. That is intended (plan §2), and the log and counter show it.

## Cut plan

The approved scope is groups 1-4 and 6-9, about 5.5 h of agent work plus closing. Group 5 is a stretch item. Cut in this order, cheapest loss first:

0. **Group 5 (centroid similarity), stretch.** It is not started unless time is left after group 9. If it is cut, its requirement "Similarity rescue in the topic gate (stretch)" is removed from the `document-analysis` delta before archive.
1. **The gate counter and the near-dup summary sentence (part of group 8; the alert suppression in group 8 stays).** The logs still carry the decision.
2. **Group 3 (cache and breaker).** Keep `EMBED_TIMEOUT_S` at 2 without the breaker.
3. **`datasketch` → own numpy MinHash** if `pip-audit` is not clean (Damian's condition) or the image size objects.

Never cut: real embeddings (groups 2 and 7) and near-dup (group 6), which together are the minimum the challenge text asks for ("usuwanie duplikatów", "embeddingów"); degradation to `model.embedder = null`; the `off_topic` log reason; the `firm_own` bypass; the alert suppression; and the loopback guard.

## Resolved questions

Answered by the coordinating session on Damian's approval, checked against `doc/Opis Wyzwania HackNation UKNF 19.11.pdf` (2026-11-21):

1. **Near-dup and alerts.** A near-dup still gets its finding and `finding.created`, but no second `finding.high_risk` for the same group and module. Its summary names the original, and its own URL stays on the finding. Reason: the documents ask for "usuwanie duplikatów" and real-time high-risk alerts, and repeat alerts would spam the live demo. This is the `finding-events` delta and decision 5.5.
2. **`unknown` source kind** is gated like `third_party`. Documents that pass flow to M1/M3. M2 covers only material "publikowanych bezpośrednio przez" firms.
3. **Near-dup sentence in `summary`:** on.
4. **`datasketch`:** kept if `pip-audit` is clean, otherwise our own numpy MinHash (cut plan 3).
5. **Gate threshold 0.45:** kept until the gold set from `analytics-eval-calibration` is calibrated. It applies only to the stretch similarity rescue.

## Open Questions

None.
