# 0318. Hosted LLM default: DeepSeek Flash, and M1's default threshold from the LLM gold run

- Status: accepted
- Date: 2026-11-22
- Deciders: agent-written from Damian's decision (relayed by the coordinating session); accepted by: pending approval of the `analytics-deepseek-default` PR
- Supersedes:
  - only the choice of hosted provider and model in [ADR 0317](0317-hosted-llm-gemma-on-gemini-api.md), and its limits (new limits below). Everything else in 0317 and [ADR 0304](0304-llm-serving.md) still holds: the OpenAI-compatible API only, env-only swap, rules-only fallback, local Ollama Gemma as the swap target, the `<thought>` strip.
  - for M1 only, [ADR 0316](0316-default-thresholds-from-evaluation.md)'s "default = best F1 of the rules-only run". M2 and M3 still follow 0316.

## Context

ADR 0317 made Gemma 4 on the Gemini API the hosted default. On 2026-11-22 the team measured it as mostly unavailable: many calls returned 503 "high demand" or 429 per-minute quota, and the successful calls took 17-41 s. On the demo stack, Gemini answered about one call in ten during the cache warm-up (`.docs/demo-analytics.md` §4). The team then tried DeepSeek Flash on its OpenAI-compatible API. The client needed no change.

Thresholds were measured rules-only so far (0316), while the stack runs with the hosted LLM on. With an LLM that answers reliably, the LLM run is the one that describes the default stack. M1 is the module whose best threshold moves.

## Evidence (measured on 2026-11-22 with the team's key, from the developer machine)

All numbers come from one session's runs on `main` 0434553b. Analytics, the API and contracts are unchanged on `main` dd30d668, where this change starts.

**Smoke test** (`https://api.deepseek.com`):
- `GET /models` returns HTTP 200 in 0.55 s, listing `deepseek-flash` ("DeepSeek-V4.1-Flash", 1M context) and `deepseek-v4-pro`.
- `POST /chat/completions` with our request shape (system + user message, `temperature: 0`, `response_format: {"type": "json_object"}`) returned 200 on three of three calls, in 1.17-1.62 s.
- `response_format` is accepted, and the content is a plain JSON object: no `<thought>` block, no fence. The model reasons internally (about 80-100 `reasoning_tokens` per call), but the reasoning is not in `content`.

**Gold-set run with the LLM** (`python eval/run.py --llm`, `LLM_TIMEOUT_S=60`, `LLM_DOC_BUDGET_S=90`, 69 documents, 91.6 s):
- 28 calls, all 200: no 4xx/5xx, no timeouts, no malformed answer, no breaker opening.
- Latency: average 3.1 s, p95 6.4 s, maximum 11.6 s.
- The run is committed as [`analytics/eval/llm-run-deepseek-flash.json`](../../analytics/eval/llm-run-deepseek-flash.json).

**End to end** (stack `iw-latest`, real demo pages, same limits plus `CLAIM_MIN_IDLE_MS=120000`):
- 91 of 92 calls returned 200. One answer was malformed ("message content is not JSON", M1): its verdicts were dropped and rules decided that chunk.
- Call latency: average 6.7 s, p50 4.7 s, p95 18.7 s, maximum 28.3 s (n = 87). Real pages are longer than gold documents.
- Whole documents took up to 53 s (icobench, 4-chunk input).
- Cache: a second pass over the seven demo documents made 0 calls.
- Fallback: with an invalid key, DeepSeek returned 401 in 0.49 s, the finding was built rules-only, and `model.llm` was `null`.

**Module curves at the committed defaults** (gold set sha256 963f834e…; cases are positive / negative):

| Module (cases) | Run | Threshold | P | R | F1 | TP / FP / FN / TN | F1 plateau |
|---|---|---|---|---|---|---|---|
| M1 (18: 10 / 8) | rules-only | 0.65 | 1.000 | 0.800 | 0.889 | 8 / 0 / 2 / 8 | 0.40-0.65 |
| M1 | rules-only | 0.75 | 1.000 | 0.700 | 0.824 | 7 / 0 / 3 / 8 | |
| M1 | DeepSeek | 0.65 | 0.909 | 1.000 | 0.952 | 10 / 1 / 0 / 7 | 0.75-0.80 |
| M1 | DeepSeek | 0.75 | 1.000 | 1.000 | 1.000 | 10 / 0 / 0 / 8 | |
| M2 (35: 23 / 12) | rules-only | 0.1 | 0.944 | 0.739 | 0.829 | 17 / 1 / 6 / 11 | 0.05-0.10 |
| M2 | DeepSeek | 0.1 | 1.000 | 0.739 | 0.850 | 17 / 0 / 6 / 12 | 0.10 only |
| M3 (18: 10 / 8) | rules-only | 0.4 | 1.000 | 0.400 | 0.571 | 4 / 0 / 6 / 8 | 0.25 only |
| M3 | DeepSeek | 0.4 | 1.000 | 0.400 | 0.571 | 4 / 0 / 6 / 8 | 0.05-0.40 |

M2 at 0.25 gives 1.000 / 0.609 / 0.757 and at 0.40 gives 1.000 / 0.478 / 0.647, the same on both runs.

## Options considered

1. **Keep Gemma 4 on the Gemini API (0317).** Open weights, closest to the task text's "Gemma4", but mostly 503/429 today. The demo would run mostly rules-only and depend on a pre-warmed cache.
2. **DeepSeek Flash on its OpenAI-compatible API.** It needs no code change, answers in seconds, and every call but one of 120 returned valid JSON. It is a hosted provider outside the EU. Whether this model's weights are published was not checked.
3. **Local Ollama only.** Fully on-premise, but `gemma3:4b` on CPU is slow and weaker. Its quality and speed were not measured.

For M1's threshold:
1. **Keep 0.65 (rules-only best F1).** With DeepSeek it raises one false alert (FP 1).
2. **0.8, the higher end of the DeepSeek plateau (0316's procedure applied to the LLM run).** Same gold-set numbers as 0.75 on both runs.
3. **0.75, on the DeepSeek plateau (Damian's choice).**

## Decision

Option 2: the hosted default is DeepSeek Flash.

```
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-flash
LLM_API_KEY=<DeepSeek API key, only in .env>
LLM_TIMEOUT_S=60
LLM_DOC_BUDGET_S=90
CLAIM_MIN_IDLE_MS=120000
```

- **Limits.** The limits are the ones measured above. 0317's 45 / 50 / 90000 would have cut the 53 s document. They satisfy [ADR 0310](0310-llm-chunking-and-budget.md) with embeddings on: (90 + 3 + `EMBED_TIMEOUT_S` 15) × 1000 = 108000 < 120000.
- **Alternatives, by `.env` only:**
  - Gemma 4 on the Gemini API (0317's lines and limits) stays a documented alternative.
  - Local Ollama `gemma3:4b` (`--profile llm`) stays the swap target.

The M1 default threshold is **0.75**. It is the lower end of the DeepSeek run's F1 plateau, where 0316's tie rule would take 0.8. On this gold set 0.75 and 0.8 give the same counts on both runs: DeepSeek 10 / 0 / 0 / 8, rules-only 7 / 0 / 3 / 8.

Rationale:
- The measured availability (1 failure in 120 calls, against about one success in ten for Gemini on the same day) makes the LLM layer usable on the demo stack, which 0317 could not.
- With the LLM on, M1 at 0.75 removes the one false alert of 0.65 at no loss of recall.
- If the LLM is down, the rules-only fallback at 0.75 keeps precision 1.0 and loses one more positive (recall 0.7 instead of 0.8).

**Where it lives.**
- `analytics/eval/thresholds.json` stays the one source, with M1 0.75. The API's `DEFAULTS` and `events.DEFAULT_THRESHOLDS` are copies, as before.
- `evaluation/runner.py` holds `LLM_MEASURED_DEFAULTS = {"M1": 0.75}` and `LLM_RUN_FILE`. `--write-thresholds` (rules-only) keeps that value for M1. It refuses one that is not on the recorded run's F1 plateau, within 0.02 of the best F1.
- `tests/test_eval_thresholds.py` checks that:
  - M1's committed value is on the recorded run's plateau;
  - the recorded run was measured on the committed gold set (sha256);
  - this build's rules-only M1 default is still the recorded run's rules-only value, 0.65. A rule change that moves it means the LLM run no longer describes the build, and it must be re-run;
  - the rules-only point at M1's default has no false positive.

Tests never call the real LLM, so the LLM curve itself is evidence, re-measured with `python eval/run.py --llm` and replaced when the gold set or the M1 rules change.

## Consequences

- **Data.** Scraped public text and firm names go to DeepSeek's endpoint instead of Google's. DeepSeek's data-use terms were not checked by the agent. This stays within ADR 0304's mentor exception, and the hand-in README must say which provider receives the text.
- **Task text.** The task names Gemma 4 and local serving. The open model is still there, as the local Ollama swap target and as the documented Gemini alternative, but it is not the hosted default. This is a trade of fit to the text for a working LLM layer on the hand-in day.
- **Cache.** The cache key includes the model, so a stack switched from Gemma to DeepSeek analyses pages again. The demo stack `iw-demo` keeps its pre-warmed Gemma cache until someone switches it.
- **Determinism.** The verdicts are not deterministic across providers. On XTB IKE, Gemma cleared R15 (`pass`, score 0.368) and DeepSeek failed it (score 0.474). An LLM run is stored as a new run (ADR 0312), and the curves above are one measurement.
- **M3.** DeepSeek's M3 best F1 (0.588 at 0.25 or below) is worse than the rules-only one (0.706 at 0.25), and 0.4 is on its plateau, so M3 stays 0.4 (0316 and the gate floor).
- **M2.** M2 stays 0.1, the best F1 of both runs.
