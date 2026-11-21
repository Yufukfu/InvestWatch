# Proposal

## Why

Stage 3 (etap 3) of analytics. The challenge document (`doc/Opis Wyzwania HackNation UKNF 19.11.pdf`, p.2) asks for preprocessing with tokens, embeddings and deduplication, and the jury gives 20% of the score to fit with the specification. Today `preprocessing.py` computes only an exact `content_hash`, and the pipeline has no topic gate: every non-empty document goes straight to routing. Step 2 of the pipeline in `.docs/analytics-plan.md` §2 (the "is this investment-related content?" gate) does not exist yet. The near-dup part of step 1 is missing too, and so are the embeddings listed in §7. The mock findings already show `model.embedder: bge-m3`, but every real finding says `null`.

This change adds those three pieces. Each has an honest fallback, so the demo never depends on an embeddings model being up.

**Order.** This change lands **after `analytics-llm-p0`**, because both edit `preprocessing.py` and `pipeline.py` (`analyze` gains the `judge` argument there, and gains `embedder` and `neardup` here). The branch `analytics/analytics-embeddings` is cut from `analytics/analytics-llm-p0` (which itself sits on `analytics-worker`, PR #26). It will be **rebased onto `main` once its parents merge**. Apply does not start before `analytics-llm-p0` group 8 (engine seam and `analyze` signature) and group 10 (the breaker it mirrors) are done. `analytics-m1-m3` also edits `pipeline.py`. Its dispatch change is independent of the gate, but whichever lands second rebases.

## What Changes

- **Embeddings client** (`analytics/src/investwatch_analytics/embeddings/`). It mirrors the `analytics-llm-p0` LLM client: `httpx`, no SDK, env only, and the same error taxonomy (`EmbedUnavailable`, `EmbedMalformed`), timeout and circuit breaker.
  - It calls the OpenAI-compatible `POST {EMBED_BASE_URL}/embeddings`, which Ollama serves under `/v1`.
  - The default model is **`bge-m3`**: open weights, MIT licence, multilingual including Polish, 1024 dimensions. It runs locally in the optional `ollama` service. A paid hosted embeddings API is not a supported configuration (ADR 0313).
  - With `EMBED_BASE_URL` empty, embeddings are off.
  - A wrong vector size, NaN values or a zero vector count as malformed.
- **Embedding cache in Redis**, keyed by `content_hash` + model (+ input length), storing float32 vectors with a TTL. A Redis error is a miss and never fails the document.
- **Degradation.** If the embedder is disabled, down, slow, malformed or breaker-open, the pipeline continues with `model.embedder = null` and the gate uses only the dictionary. `model.embedder` is set to `EMBED_MODEL` only when a vector was actually used.
- **Topic gate** (plan §2 step 2), between preprocessing and routing:
  - Signals: an investment-vocabulary dictionary (YAML, diacritic-insensitive stems such as `inwest*`, `zysk*`, `stopa zwrotu`, `CFD`, `forex`, `krypto*`, `obligacj*`, `ETF`, `makler*`) plus cosine similarity to class centroids built from seed phrases.
  - The threshold is low and asymmetric: a document is dropped only when the dictionary finds nothing **and** the similarity (if available) is below `GATE_SIM_THRESHOLD`.
  - `firm_own` documents bypass the gate, because M2 must judge every firm page.
  - A dropped document is logged with reason `off_topic` and its gate figures, and is counted in Redis. It is never a silent loss.
- **Near-duplicate detection** (plan §2 step 1):
  - MinHash with `datasketch` over word 5-shingles of the normalized text, plus our own LSH banding in Redis (ADR 0314).
  - A near-dup is **still analyzed and still gets its own finding**: each publication is separate evidence for UKNF, and the `Finding` contract cannot change.
  - The group is recorded in Redis (`iw:neardup:v1:…`: a document maps to its group, the group to its members), is logged, and is named in one Polish sentence of the finding `summary`.
  - This prepares the URL-level grouping follow-up from Kacper's #26 review and issue #33, without changing a contract.
- **Wiring.** `analyze(..., judge=None, embedder=None, neardup=None)` stays pure apart from the injected objects. The worker builds both from env with its Redis client. The CLI builds the embedder without a cache and has no near-dup index, and `--no-embed` forces embeddings off. `analytics/compose.yaml` passes `EMBED_*` and `GATE_*`.
- **Dependencies:** `datasketch` (MIT, pulls `numpy` and `scipy`). `httpx` already comes with `analytics-llm-p0`. Both are scanned with `pip-audit`.
- **ADRs:** 0313 (embeddings model and serving) and 0314 (topic gate and near-dup strategy).

### Asks for infra (Kacper owns `infra/`; this change does not edit it)

1. The `ollama-pull` one-shot (profile `llm`) also pulls `bge-m3` (about 1.2 GB), with the pull list overridable by env (for example `OLLAMA_MODELS="gemma3:4b bge-m3"`).
2. `OLLAMA_MAX_LOADED_MODELS=2` on `ollama`, so that Gemma and `bge-m3` do not evict each other on every document, and `OLLAMA_KEEP_ALIVE` long enough for a demo (for example `30m`).
3. The context length is related to issue #32 (`OLLAMA_CONTEXT_LENGTH=8192`). The embedder truncates its own input to `EMBED_MAX_CHARS`, so it does not depend on #32, but the same setting covers `bge-m3`.
4. The infra spec "Optional local LLM behind a profile" names only `gemma3:4b`. Kacper updates that scenario when he adds the model.

Until the asks land, `bge-m3` can be pulled by hand (`docker compose exec ollama ollama pull bge-m3`), or the embedder stays off and the gate runs on the dictionary. Both are valid states.

### Related, not changed here

- **Issue #31** (NFC vs NFKC `content_hash`). Cache keys use analytics' own preprocessing hash (the same as the LLM cache in `analytics-llm-p0`), so analytics stays self-consistent. If #31 makes analytics read the stored hash, the caches go cold once, which is harmless. This change does not redefine the hash.
- **Issue #33** (several findings per document) and the URL-level grouping follow-up are where the near-dup groups would surface in the API and UI. This change only records the groups.

## Capabilities

### New Capabilities
- `text-embeddings`: env-only embeddings client for an OpenAI-compatible `/embeddings` endpoint, vector validation, Redis cache, breaker and degradation, `model.embedder`.

### Modified Capabilities
- `document-analysis`: ADDED requirements only:
  - the investment topic gate;
  - near-duplicate detection and grouping;
  - the embedder recorded on findings.

  `Preprocessing` and `M2 finding assembly`, which `analytics-llm-p0` modifies, are not touched. The new behaviour sits in separate requirements so that the two changes archive without a merge.

## Impact

- **Module owner:** Damian (`analytics/`). No `api/`, `web/`, `scraper/` or `infra/` file changes. The infra items are asks.
- **Contracts:** none changed. `model.embedder` (string or null) already exists in `finding.schema.json` v1. A near-dup sentence in `summary` is free text. No REST route and no event changes. A gated-out document publishes nothing, the same as an `empty_text` skip today. `contracts/mocks` stay untouched.
- **Redis keys (analytics-internal, new):**
  - `iw:emb:v1:*` (vector cache, TTL);
  - `iw:neardup:v1:*` (band buckets, signatures, group map, TTL);
  - `iw:stats:gate` (passed and dropped counters).

  They are documented in `analytics/README.md` and `.docs/integration-plan.md` §7 conventions, if Redis keys are listed there.
- **Code:** `embeddings/` (new), `gate.py` and `gate_terms.yaml` (new), `neardup.py` (new), `pipeline.py`, `modules/m2.py` summary (and M1/M3 builders if `analytics-m1-m3` has landed), `config.py`, `worker.py`, `cli.py`, `analytics/compose.yaml`, `analytics/.env.example`, `requirements*.txt`, `pyproject.toml`.
- **Behaviour change:** `third_party` and `unknown` documents with no investment signal are no longer analyzed. Today that is a no-op for them (`module_not_implemented`). With `analytics-m1-m3` it would cut false M1/M3 findings on off-topic posts.

## Out of scope

- A vector database or ANN index (Redis Stack, pgvector). Similar-ad grouping for the dashboard (plan §7 "dashboard bonus") is a follow-up.
- Exposing near-dup groups in the REST API or the dashboard (issue #33, Kacper and the API follow-up).
- Changing the `content_hash` definition (issue #31).
- Using embeddings inside M1-M3 rules or as LLM retrieval.
- Editing `infra/`, `contracts/`, the STATUS files or other changes' branches.
