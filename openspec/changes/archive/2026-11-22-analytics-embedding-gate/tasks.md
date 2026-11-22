# Tasks

Requested by Damian on 2026-11-22. Feature freeze 08:00, so if time runs short, cut as `design.md` "Cut plan" says. No test calls a real model: tests use `FakeEmbedder` with hand-made vectors and `fakeredis`. Every group starts with its failing test and ends with a mutation check (iw-commit-cycle step 3).

## 1. Seeds, settings and the rescue core (~45 min)

- [x] 1.1 Failing tests: `load_terms` rejects `centroids` without `off_topic` or with `off_topic` only; `GATE_EMBED_MIN_MARGIN` outside [0, 1] and `GATE_EMBED_MIN_CHARS` ≤ 0 are rejected; `GateEmbedding.warm()` builds normalized class means from `FakeEmbedder`, stops on the first failed seed, and reuses cached seeds; `rescue()` returns `embedding` pass/drop by margin and `dictionary_only_fallback` with no centroids or a failed vector
- [x] 1.2 `off_topic` seeds (no dictionary hit) and on-topic seeds in `gate_terms.yaml`; `GateSettings.embed_min_margin` / `embed_min_chars` (replacing the unused `GATE_SIM_THRESHOLD`; compose and `.env.example` updated); `gate_embedding.py` (`GateEmbedding`, `decide`); `GateDecision.path`, `margin`
- [x] 1.3 Mutation check; `mutations: 29 tried, 28 caught`, then the survivor (dropping the `off_topic` check when two on-topic classes exist) got its test case: `mutations: 3 tried, 3 caught` on the seed-class guard

## 2. Pipeline wiring (~40 min)

- [x] 2.1 Failing tests: the "Embedding rescue in the topic gate" scenarios end to end through `analyze_document` (rescued post routed and its findings carry `model.embedder`; the document embedded once; a dictionary hit never calls the embedder for the gate; a short text not embedded; `firm_own` unaffected; gold M1/M3 positives never dropped with an off-topic-voting embedder); log line has `gate_path`, `similarity`, `margin`, no text; degrade messages once per change of reason
- [x] 2.2 `pipeline.py`: the rescue after `evaluate`, `EmbedOutcome` reused; `Gate` carries the optional `GateEmbedding`
- [x] 2.3 Mutation check; `mutations: 5 tried, 5 caught` (after adding the stored-hash and failed-outcome assertions that the first draft lacked)

## 3. Worker, CLI, counter, compose (~40 min)

- [x] 3.1 Failing tests: worker warms the centroids at start and between messages (rate-limited, never inside `_process`); counter path fields and `rescued`; Redis error on the counter is not raised; CLI builds and warms with `EMBED_BASE_URL`, none with `--no-embed`; compose passes `GATE_EMBED_*` with empty meaning the default
- [x] 3.2 `worker.py`, `cli.py`, `gate.count_decision`, `analytics/compose.yaml`
- [x] 3.3 Mutation check; `mutations: 11 tried, 10 caught`; the survivor (warm inside `_process`) showed the test never reached the analysis, fixed: `mutations: 1 tried, 1 caught`. Not covered by a test: the two wiring lines in `worker.main` (checked in the manual run, task 4.3)

## 4. Calibration and the real run (~45 min)

- [x] 4.1 `analytics/eval/gate_check.jsonl` (labelled, no seed repeated) and `analytics/eval/gate_calibrate.py`; run against real `bge-m3`; set the default `GATE_EMBED_MIN_MARGIN`; precision and recall into `design.md` §4 (0.03: P 1.0, R 1.0 on 30 no-hit lines); `tests/test_gate_calibrate.py` pins the set and the sweep: `mutations: 4 tried, 3 caught`, the survivor (`>=` to `>` in the sweep) got a boundary row, then `mutations: 4 tried, 4 caught`
- [x] 4.2 `eval/run.py` recall unchanged (it calls `analyze` without a gate); `test_eval_thresholds` green (18 passed); full suite 2122 passed, 125 skipped
- [x] 4.3 Manual run with `bge-m3` (CLI against a standalone Ollama `bge-m3`, then the real `--profile llm` stack once Docker networks were freed; see follow-ups.md). The run found the rounding mismatch F7, fixed in b47e9102 with a test: `mutations: 1 tried, 1 caught`: latency (cold, warm, centroid build), decisions on the mock documents and the demo sources (xtb, comparic, icobench, moneteo, tradingview, ey, KNF warnings page); results in the PR body

## 5. Closing

- [x] 5.1 iw-docs-update: ADR 0314 amendment, `analytics/README.md`, `.docs/analytics-plan.md` §2, `.docs/status/platform.md`, `.env.example` comment if any; `docs-check` clean
- [x] 5.2 iw-ai-log entry
- [x] 5.3 iw-pr-review; follow-ups.md
- [x] 5.4 Archive (last commit)
