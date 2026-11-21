# 0314. Topic gate and near-duplicate strategy

- Status: accepted
- Date: 2026-11-21
- Deciders: agent-written for Damian (change `analytics-embeddings`, stage 3); accepted by Damian via the PR of that change (depends on [0313](0313-embeddings-model-and-serving.md))

## Context

`.docs/analytics-plan.md` §2 plans:
- step 1, near-dup with SimHash or MinHash (`datasketch`);
- step 2, a gate "is this investment-related content?" built from a dictionary plus embedding similarity to class centroids, with "low threshold – we prefer to let content through".

The challenge (`doc/Opis Wyzwania HackNation UKNF 19.11.pdf` p.2) names deduplication explicitly.

Constraints:
- The `Finding` contract is frozen (v1), and findings are unique per `(document_id, module)` (ADR 0307, `finding-storage` spec).
- A changed page gets a new document and a new finding. Kacper's #26 review asked for URL-level grouping as a follow-up, and issue #33 asks the UI to show several findings per document.
- Redis 8 without Stack has no vector index.
- The embedder may be off ([ADR 0313](0313-embeddings-model-and-serving.md)).

## Options considered

Gate:
1. **Dictionary only.** Deterministic and free. It misses posts that avoid the vocabulary.
2. **Dictionary or embedding, where a document is dropped only when both say no.** The embedding can only rescue a document, so recall stays high and the gate still works with the embedder off.
3. **A classifier with a negative centroid, or the LLM as gate.** Either can drop on-topic text by comparison. The LLM costs one call per document for a yes/no question, and plan §1 says rules before the LLM.

Near-dup:
4. **MinHash (`datasketch`) with our own LSH banding in Redis.** Jaccard over word shingles handles reposts with small edits and partial overlap. It needs no embedder and can be tested with `fakeredis`. `datasketch`'s own `MinHashLSH` Redis storage opens its own connection from host and port config, so it cannot use the worker's client or `fakeredis`.
5. **SimHash.** A smaller index, but weaker on short posts and on partial overlap.
6. **Embedding cosine.** It needs a vector index (pgvector would mean a schema change, Redis Stack a new image), and it does not work with the embedder off.

What a near-dup does:
7. **Drop or merge it into the first finding.** That loses separate publications UKNF must see, and merging needs a contract change.
8. **Analyze it as usual, and record the group in Redis, the log and the summary text.** No contract change, and it is the data that URL-level grouping (#33) needs later.

## Decision

- **Gate: option 2.**
  - A document is dropped only when the diacritic-insensitive dictionary (`gate_terms.yaml`, plus a registry firm match) has no hit and the similarity to the positive centroids is missing or below `GATE_SIM_THRESHOLD` (0.45, to calibrate on the gold set).
  - `firm_own` bypasses the gate, because M2 must check every firm page.
  - A drop is logged with reason `off_topic` and its figures, and counted in `iw:stats:gate`. The `documents` row stays, so it can be re-analyzed.
- **Near-dup: options 4 and 8.**
  - MinHash with 128 permutations over word 5-shingles and 32 bands × 4 rows, with candidates verified at Jaccard ≥ 0.8.
  - The group id is the earliest member's `document_id`, under `iw:neardup:v1:*` with a 30-day TTL.
  - A near-dup is still analyzed and gets its own findings. Its summary names the number of near-identical materials.

Rationale from the evidence above:
- Option 2 is the only gate that matches the plan's "prefer to let content through" and still works with the embedder off.
- Option 4 is the only near-dup technique that works without the embedder and is testable with `fakeredis`.
- Option 8 is the only handling that keeps the frozen contract and every publication.

## Consequences

- With M1/M3 live, off-topic third-party posts no longer produce findings. The log and the counter make each drop visible.
- `datasketch` adds `numpy` and `scipy` to the image. Our own numpy MinHash is the fallback if that is a problem.
- Near-dup groups do not merge transitively. A document joins its best-matching group, which is an accepted error.
- Exposing groups in the API or UI is a follow-up (issue #33, the URL-level grouping item). A nullable `group_id` in a later contract version is one path.
- Whether a near-dup fires `finding.high_risk` again stays as it is today (yes). Suppressing repeat alerts would modify `finding-events` and is left to Damian.
