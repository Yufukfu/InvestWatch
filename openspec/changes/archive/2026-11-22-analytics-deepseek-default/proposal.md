# Proposal

## Why

The hosted default LLM of [ADR 0317](../../../.docs/decisions/0317-hosted-llm-gemma-on-gemini-api.md), Gemma 4 on the Gemini API, was mostly unavailable on 2026-11-22: many calls returned 503 "high demand" or 429, and the ones that succeeded took 17-41 s. DeepSeek Flash on its OpenAI-compatible API answered 119 of 120 calls with valid JSON, in 3-7 s on average, with no client change.

Damian decided two things:
- the hosted default is DeepSeek Flash;
- the M1 default threshold is 0.75.

The 0.75 value lies on the F1 plateau of the DeepSeek gold run (0.75-0.8). Until now every default came from the rules-only run (ADR 0316), so the gold-set evaluation spec must say where an LLM-measured default comes from and how it stays checked.

## What Changes

- **ADR 0318.** It records the provider switch, which supersedes ADR 0317's provider, model and limits, and M1's default from the LLM run, which supersedes ADR 0316's rules-only rule for M1 only. It gives the evidence: the smoke test, the eval tables for both runs and the end-to-end stats.
- **Config, docs only.** `LLM_BASE_URL=https://api.deepseek.com`, `LLM_MODEL=deepseek-flash`, limits `LLM_TIMEOUT_S=60`, `LLM_DOC_BUDGET_S=90`, `CLAIM_MIN_IDLE_MS=120000`. These go in `analytics/.env.example`, the root `.env.example`, `analytics/README.md`, `analytics/CLAUDE.md`, `analytics/compose.yaml` comments and `.docs/analytics-plan.md`. Gemma 4 on the Gemini API stays a documented alternative, and local Ollama `gemma3:4b` stays the swap target.
- **M1 default 0.75:**
  - `analytics/eval/thresholds.json`, the API's `DEFAULTS` and `events.DEFAULT_THRESHOLDS` change to M1 0.75;
  - the DeepSeek gold run is committed as `analytics/eval/llm-run-deepseek-flash.json`;
  - `evaluation/runner.py` adds `LLM_MEASURED_DEFAULTS = {"M1": 0.75}`, which `--write-thresholds` keeps and refuses when it is off the recorded run's F1 plateau;
  - `tests/test_eval_thresholds.py` checks the value against that run, the run against the gold set and M1's rules-only default, and the rules-only fallback for false positives.
- **Spec delta**: `gold-set-evaluation`, requirement `Default thresholds from the evaluation`.

## Out of scope

- **Client code.** DeepSeek needs none. The `<thought>` strip and the bare-array reading stay for Gemma.
- **Hand-in material.** `.docs/presentation-analytics.md` and `.docs/hand-in.md` are updated by another session from these numbers.
- **The demo stack `iw-demo`** and its pre-warmed Gemma cache are not touched here.
- **M2 and M3 defaults** (0.1, 0.4) are unchanged, because the DeepSeek run confirms them.
- **The mock server's thresholds** (`contracts/mocks/thresholds.json`) stay untouched, by rule.
