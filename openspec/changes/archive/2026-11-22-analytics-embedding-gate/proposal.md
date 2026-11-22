# Proposal

## Why

Damian asked for "wykorzystanie embeddingów w bramkowaniu wiadomości". Today the topic gate (ADR 0314) uses the dictionary only. `analytics-embeddings` (#81) shipped the `bge-m3` embedder, its cache and its breaker, but it cut group 5 (centroid similarity) for time and removed that requirement. So a real investment post that uses none of the `gate_terms.yaml` vocabulary is dropped as `off_topic` (follow-ups R23, R41). The challenge asks for embeddings in preprocessing (Opis p.2). Today they only fill `model.embedder`; they decide nothing.

## What Changes

- **Embedding rescue in the gate.** The dictionary stays the first, cheap decision. Embeddings decide only the case it leaves open: a gated (`third_party` / `unknown`) document with **no** dictionary hit and at least `GATE_EMBED_MIN_CHARS` characters. They can only **rescue**. A document the dictionary passes is never re-judged, so embeddings can never drop it.
- **Two kinds of seed lines.** `gate_terms.yaml` `centroids` gets a reserved `off_topic` class (generic news, shopping, sports, recipes) next to the existing on-topic classes. Every line is short and synthetic, with no scraped or personal data. A centroid is the normalized mean of its seed vectors. The seeds are embedded with the same embedder and cached under the existing `iw:emb:v1:*` keys.
- **Decision.** `margin = max cos(on-topic class centroids) − cos(off_topic centroid)`. The gate rescues when `margin ≥ GATE_EMBED_MIN_MARGIN`. The default is measured on a small labelled check set, and its precision and recall are recorded in `design.md`.
- **Degrade.** The gate stays dictionary-only when there is no embedder, the breaker is open, an embedding fails or the centroids are not built yet. It logs the reason once per change and never raises. The centroids are built outside any message: at start-up, then retried between messages at most once per breaker cooldown. A document still costs one embedding call, and the claim-idle budget check does not change.
- **Visibility.** Each decision has a `path`: `dictionary`, `embedding` or `dictionary_only_fallback`. The path goes into the skip log line (`gate_path`, `similarity`, `margin`) and into `iw:stats:gate` as the new fields `path_dictionary`, `path_embedding`, `path_dictionary_only_fallback` and `rescued`. The existing fields `passed` / `dropped` / `bypassed` keep their meaning. No contract changes (`contracts/` untouched).
- **Reuse.** The document vector the gate computes is the one the pipeline already uses for `model.embedder`, so a document is never embedded twice.

## Capabilities

- `document-analysis`: MODIFIED "Dropped documents are logged" and "Gate counters"; ADDED "Embedding rescue in the topic gate" and "Embedding gate degrades to the dictionary".

## Impact

- `analytics/src/investwatch_analytics/`:
  - `gate.py`: decision path, rescue step.
  - new `gate_embedding.py`: centroids, margin.
  - `gate_terms.yaml`: `off_topic` seeds.
  - `config.py`: `GATE_EMBED_MIN_MARGIN`, `GATE_EMBED_MIN_CHARS`.
  - `pipeline.py`: embeds before the decision only when needed.
  - `worker.py`, `cli.py`: build and warm the centroids.
- `analytics/compose.yaml`: passes the new env.
- `analytics/eval/`: `gate_check.jsonl` (labelled check set) and `gate_calibrate.py` (manual calibration).
- Docs: ADR 0314 amendment, `analytics/README.md`, `.docs/analytics-plan.md` §2, the status file.
- Nothing in `contracts/`, `web/`, `scraper/` or the mocks.
