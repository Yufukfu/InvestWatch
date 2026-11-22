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
4. **MinHash (the `datasketch` algorithm) with our own LSH banding in Redis.** Jaccard over word shingles handles reposts with small edits and partial overlap. It needs no embedder and can be tested with `fakeredis`. `datasketch`'s own `MinHashLSH` Redis storage opens its own connection from host and port config, so it cannot use the worker's client or `fakeredis`.
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
  - A near-dup is still analyzed and gets its own findings. Its summary names the original's URL, and its own `url` stays on the finding.

Rationale from the evidence above:
- Option 2 is the only gate that matches the plan's "prefer to let content through" and still works with the embedder off.
- Option 4 is the only near-dup technique that works without the embedder and is testable with `fakeredis`.
- Option 8 is the only handling that keeps the frozen contract and every publication.

## Consequences

- With M1/M3 live, off-topic third-party posts no longer produce findings. The log and the counter make each drop visible.
- No `datasketch` at runtime: `import datasketch` loads scipy (about 115 MB installed) through its LSH module, so the MinHash is our own numpy code implementing datasketch's legacy scheme value for value (checked against datasketch 2.0.0 before removing it). Only numpy is added to the image.
- Near-dup groups do not merge transitively. A document joins its best-matching group, which is an accepted error.
- Exposing groups in the API or UI is a follow-up (issue #33, the URL-level grouping item). A nullable `group_id` in a later contract version is one path.
- A near-dup does not fire a second `finding.high_risk` for the same group and module (Damian's decision). The first alert claims `iw:neardup:v1:alerted:{group}:{module}` with `SET NX`, and a Redis error fails open. The challenge asks for "usuwanie duplikatów" and real-time high-risk alerts, and a repeat alert per copy would spam the live demo. `finding.created` and the copy's own URL stay. This modifies the `finding-events` spec.
- The embedding similarity in the gate is a stretch item in the first implementation. Until it lands, the gate is dictionary-only, which is option 1 with option 2's interface.

## Amendment (2026-11-22, change `analytics-embedding-gate`)

Damian asked for embeddings in the gate ("wykorzystanie embeddingów w bramkowaniu wiadomości"), so the rescue of option 2 is now built. One part of the decision above changes: **the rescue compares against an `off_topic` centroid as well as the on-topic ones**.

- **Why the off-topic centroid is safe here.** Option 3 was rejected because a negative centroid "can drop on-topic text by comparison". In this design the embedding is consulted only for a document the dictionary already drops (no hit, at least `GATE_EMBED_MIN_CHARS` characters). It can only turn a drop into a pass, so the off-topic centroid can make a rescue harder but can never cause a drop.
- **Why it is needed.** Under `bge-m3`, unrelated Polish texts sit 0.4-0.55 cosine from the on-topic centroids. The measured on-topic similarity of off-topic lines in `analytics/eval/gate_check.jsonl` overlaps with that of on-topic lines, so an absolute cosine threshold such as the old `GATE_SIM_THRESHOLD` (0.45) cannot separate them. The margin `max cos(on-topic class) − cos(off_topic)` does.
- **Rule.** A no-hit gated document passes when `margin ≥ GATE_EMBED_MIN_MARGIN`. The default is 0.03, measured with `bge-m3` on the 30 no-hit lines of `gate_check.jsonl`: 0.03 gives precision 1.0 and recall 1.0, 0.02 gives precision 0.91, and 0.04 gives recall 0.9 (`analytics/eval/gate_calibrate.py`). `GATE_SIM_THRESHOLD` was never read and is replaced, not kept.
- **Degradation.** With no embedder, the breaker open, a failed vector or no centroids, the gate stays dictionary-only (path `dictionary_only_fallback`). The centroids are built between messages, never inside one, so a document still costs at most one embedding call and the claim-idle budget is unchanged.
- **Visibility.** The decision path (`dictionary`, `embedding`, `dictionary_only_fallback`) is in the skip log line and in `iw:stats:gate` (`path_*`, `rescued`).
- **Limits.** The check set is small and synthetic, and the seed lines are a few per class. Both are data (`gate_terms.yaml`, `gate_check.jsonl`), the margin is env, and `GATE_ENABLED=false` stays the kill switch.
