# Design

## Context

- **Gate.** `gate.py` (ADR 0314) drops a `third_party` / `unknown` document only when `dict_hits == 0`. `firm_own` bypasses it, and `GATE_ENABLED=false` turns it off.
- **Embedder.** `embeddings/embedder.py` never raises. It returns `EmbedOutcome(vector|None, model|None, status)`, has a Redis cache keyed on the stored `content_hash`, and has a breaker. Today the pipeline runs it **after** the gate, once per passing document.
- **Default stack.** It runs without `--profile llm`, so `EMBED_BASE_URL` is usually empty and the embedder is `None`.
- **Claim-idle budget.** The check is `(LLM_DOC_BUDGET_S + 3 + EMBED_TIMEOUT_S) * 1000 < CLAIM_MIN_IDLE_MS`, that is 58 s against 60 s at the defaults. A message has no room for a second embedding call.
- **No negative class, revisited.** The archived design (§4) rejected a negative class, because a non-financial centroid would make the gate drop by comparison. That only matters if embeddings can overrule a dictionary pass. Here they decide only documents the dictionary already drops. The off-topic centroid can only make a rescue harder, never cause a drop. It also turns "similar to finance" into "more finance than not". Under `bge-m3`, Polish texts all sit about 0.3-0.5 cosine apart, so an absolute threshold alone separates them poorly.

## Goals / Non-goals

- **Goal:** rescue vocabulary-free investment posts (an offer, a signal group, "napisz na priv") without ever losing a dictionary pass.
- **Goal:** the default stack (no embedder) behaves exactly as today, apart from new counter fields.
- **Non-goal:** replacing the dictionary, changing `firm_own`, routing or the modules, or an LLM gate.

## Decisions

### 1. Where embeddings decide

`evaluate()` stays pure and returns the dictionary decision. A new step, `GateEmbedding.rescue()`, runs only when:

- the decision is `off_topic` (a gated source, `dict_hits == 0`, the gate enabled);
- the text is at least `GATE_EMBED_MIN_CHARS` characters long (default 40);
- a gate embedding is configured.

There is no "borderline" band above zero hits. One hit already passes, and the rescue can only pass, so such a band would change nothing.

| Case | `reason` | `path` |
|---|---|---|
| `dict_hits > 0` | `dictionary` (pass) | `dictionary` |
| no hit, text shorter than the minimum | `off_topic` | `dictionary` |
| no hit, vector and centroids present | `embedding` (pass) or `off_topic` | `embedding` |
| no hit, no embedder / breaker open / failed vector / no centroids | `off_topic` | `dictionary_only_fallback` |
| `firm_own`, gate disabled | as today | none (not counted as a path) |

### 2. Centroids

- **Seed classes.** `gate_terms.yaml` `centroids` holds named classes of seed lines. `off_topic` is a reserved name. When `centroids` is non-empty it must contain `off_topic` and at least one other class, or loading fails at start-up.
- **Seed lines.** Four short synthetic Polish lines per on-topic class and eight `off_topic` lines (news, sports, shopping, recipes, weather, hobbies). The dictionary is broad, so 8 of the 12 on-topic lines contain a term anyway; that is fine, since a centroid describes the topic, not the miss. `off_topic` lines must have no dictionary hit (a test checks it). `eval/gate_check.jsonl` never repeats a seed.
- **`warm()`.**
  - Embeds every seed through the same `Embedder.embed(seed, content_hash(seed))`. The vectors are cached in `iw:emb:v1:{variant}:{hash}`, so a worker restart costs Redis reads only.
  - Builds one normalized mean per class and keeps it in memory.
  - On the first failed seed it stops, keeps no centroids and records the reason.
- **When `warm()` runs.**
  - Once at start-up (worker and CLI).
  - Then from the worker at the top of `run_once`, **between messages**: at most once per `EMBED_BREAKER_COOLDOWN_S` while no centroids exist, and not at all once they are built.
  - The pipeline never builds centroids. A message therefore costs at most one embedding call, as today, and the claim-idle check is unchanged.
- **Model swap.** A different model changes the cache variant. The centroids live per process and come from the configured model.

### 3. Decision

- `on = max over on-topic classes cos(v, c)`, `off = cos(v, c_off_topic)`, `margin = on − off`.
- The gate rescues iff `margin ≥ GATE_EMBED_MIN_MARGIN`.
- The log line carries `similarity = on` and `margin`, rounded to 3 places.
- The max over classes, rather than one pooled centroid, keeps a small class such as `advisory_service` from being averaged away.
- **One env name.** `GATE_SIM_THRESHOLD` (default 0.45, forwarded by `analytics/compose.yaml`) was never read by any code path: it was reserved for the cut group 5. It is **replaced** by `GATE_EMBED_MIN_MARGIN`, not kept alongside it. The meaning changed (a margin between two cosines, in [0, 1], default 0.03, not an absolute cosine), so reusing the old name would mislead. An old `.env` that still sets it starts normally and the value is ignored. `GATE_EMBED_MIN_CHARS` (positive integer, default 40) is new. Both are forwarded in `analytics/compose.yaml`, documented in `analytics/.env.example` and the README, and a test checks that every `GATE_*` variable `config.py` reads is forwarded by compose.

### 4. Calibration

- **Check set.** `analytics/eval/gate_check.jsonl` has about 40 labelled synthetic lines, none of them a seed:
  - on-topic lines with no dictionary hit;
  - off-topic lines;
  - hard negatives (a bank's opening hours, a sports "transfer", a shop "promocja").

  The gold set's gated documents are added to it.
- **Script.** `analytics/eval/gate_calibrate.py` runs by hand against a real embedder. It prints the margin of every no-hit item and the precision and recall for each candidate margin. The default is the smallest margin with precision ≥ 0.9 on the check set, rounded toward recall. The result goes into this section before archive.
- **Result (2026-11-22, `bge-m3` in Ollama on CPU, `gate_check.jsonl`: 19 on-topic and 20 off-topic lines).** Nine on-topic lines already pass on the dictionary. The sweep runs over the 30 no-hit lines (10 on-topic, 20 off-topic):

  | margin | precision | recall | tp / fp / fn |
  |---|---|---|---|
  | 0.00 | 0.769 | 1.0 | 10 / 3 / 0 |
  | 0.02 | 0.909 | 1.0 | 10 / 1 / 0 |
  | **0.03** | **1.0** | **1.0** | 10 / 0 / 0 |
  | 0.04 | 1.0 | 0.9 | 9 / 0 / 1 |
  | 0.06 | 1.0 | 0.7 | 7 / 0 / 3 |
  | 0.10 | 1.0 | 0.6 | 6 / 0 / 4 |

  The on-topic margins range from 0.039 to 0.200. The highest off-topic ones are a "like and tag a friend" giveaway (0.023), a used-bike ad (0.016) and a "13th salary" news line (0.0). The default is **0.03**: the smallest margin with precision ≥ 0.9 that keeps recall at 1.0. The gap to the nearest errors is only about 0.01 on each side, so a different model or seed set must be re-calibrated (`eval/gate_calibrate.py`).
- **Gold set through the gate** (gated documents only, computed without a registry match, so the dictionary is weaker here than in production): every M1/M3 positive passes. Four vocabulary-free M1 positives (`m1-finfluencer-ref-link`, `m1-utm-link-only`, `m1-cta-link-in-bio`, `m1-giveaway`) have no dictionary hit and are rescued with margins 0.082-0.117. In production their registry match also passes them.
- **Existing eval.** `eval/run.py` and `test_eval_thresholds` call `analyze` without a gate, so this change cannot affect them. A new test runs every gold M1/M3 positive through the gate with an embedder that votes off-topic, and asserts that none is dropped (all of them pass on the dictionary).

### 5. Degrade and logging

- **No embedder.** `GateEmbedding` is not built. Every no-hit drop of at least `GATE_EMBED_MIN_CHARS` characters has path `dictionary_only_fallback`; a shorter one keeps `dictionary`, as with an embedder. Start-up logs one INFO line, `embedding gate off`, with `reason: embedder_disabled`.
- **Breaker open, failed vector or no centroids.** The path is `dictionary_only_fallback`.
  - One WARNING `embedding gate degraded`, with the reason (`breaker_open`, `embed_timeout`, `no_centroids`, …), is logged only when the reason differs from the last one.
  - One INFO `embedding gate restored` is logged when the rescue works again.
  - The worker is never slowed beyond the one call it already makes: the breaker short-circuits while open.
- **Vector reuse.** The document's `EmbedOutcome` from the gate is passed on to the findings (`model.embedder`), so a rescued document is not embedded twice.

### 6. Counter

- `count_decision` keeps `passed` / `dropped` / `bypassed`.
- It adds `path_<path>` (not for a bypass or a disabled gate) and `rescued`, sent in one pipeline (`transaction=False`).
- A Redis error is logged and never raised.
- The new fields are additive. No consumer reads the hash today, and `contracts/` does not describe it.

## Risks / Trade-offs

- **A spam post is rescued** (false positive). It then goes to M1/M3, which find nothing and build no finding (`no_signals`). The cost is CPU, not a wrong alert.
- **Centroids built from a few lines are fragile.** They are data in YAML, the margin is env, and `GATE_ENABLED=false` stays the kill switch.
- **CI never runs a real embedder.** Tests use `FakeEmbedder` with hand-made vectors. The manual run with `bge-m3` is reported in the PR.

## Cut plan

If time runs short by about 06:30, ship groups 1-3 (the rescue with a safe default margin). Move calibration refinements and the counter path fields to `follow-ups.md`.
