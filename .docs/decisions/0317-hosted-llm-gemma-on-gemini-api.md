# 0317. Hosted LLM default: Gemma 4 on the Gemini API

- Status: accepted
- Date: 2026-11-21
- Deciders: agent-written from Damian's decision (relayed by the coordinating session); accepted by Damian via the `analytics-llm-p0` PR
- Supersedes: only the choice of hosted provider in [ADR 0304](0304-llm-serving.md). Everything else in 0304 still holds: the OpenAI-compatible API only, env-only swap, rules-only fallback, local Ollama as the swap target.

## Context

[ADR 0304](0304-llm-serving.md) made a hosted OpenAI-compatible model the default during the hackathon, under a mentor exception, with OpenAI as the example provider. The task text (`doc/Opis Wyzwania HackNation UKNF 19.11.pdf`, section 5) asks for free, open models: it names "Gemma4 lub… BERT" and "vllm, lama.cpp lub ollama". The jury scores fit to that specification (20%). Damian decided on 2026-11-21 that the hosted default is Gemma 4 served by Google's Gemini API, because it is an open-weights model, which is closer to the task text than a closed one.

The analytics client speaks only the OpenAI-compatible chat completions API ([ADR 0309](0309-llm-prompt-and-cache-contract.md)). The Gemini API has an OpenAI-compatible endpoint at `https://generativelanguage.googleapis.com/v1beta/openai`. Google's documentation for that endpoint does not mention Gemma, and Gemma's own documentation uses the native `generateContent` API, so this ADR relies on measurement, not on documentation.

## Evidence (task 12.4, measured on 2026-11-21 with the team's key, from the developer machine)

- `GET {base}/models` returns HTTP 200 in about 1.4 s, with 65 models. These include `models/gemma-4-31b-it` and `models/gemma-4-26b-a4b-it`. No smaller hosted Gemma 4 size is listed.
- `POST {base}/chat/completions` with a system and a user message, `temperature: 0` and `response_format: {"type": "json_object"}` was **accepted**: HTTP 200, with no 400 on any of these parameters.
- **Gemma 4 prefixes the answer with a reasoning block.** The content starts with `<thought>…</thought>`, even in JSON mode, and the agreed JSON object follows it. The client now strips one leading `<thought>` block, and a ```json fence, before parsing. Any other text around the object is still malformed ([ADR 0309](0309-llm-prompt-and-cache-contract.md) is unchanged: the object shape is the contract).
- **Availability was poor at measurement time.** About half the calls returned HTTP 503 `UNAVAILABLE` ("This model is currently experiencing high demand"). One `gemma-4-31b-it` call exceeded a 60 s read timeout.
- **Latency of the successful calls:** `gemma-4-26b-a4b-it` about 9.5 s; `gemma-4-31b-it` 57 s, for a one-line test document.
- **CLI run on the eight mock documents** (`python -m investwatch_analytics.cli contracts/mocks/documents.json`, fictional seed registry, `LLM_TIMEOUT_S=60`):
  - `gemma-4-31b-it`: 3 of 3 calls returned 503. The breaker opened and every finding stayed rules-only (`model.llm = null`). 33 s in total.
  - `gemma-4-26b-a4b-it`: 3 of 5 calls returned 200, in 14.8 s, 29.1 s and 20.1 s; one returned 503 and one hit the 60 s timeout. 131 s in total.
  - The verdicts were sensible, with verified quotes: S1.5 `fail` on both finfluencer posts, S1.4 `pass`, S3.3 and S3.4 `fail` on the family-office offer.
- **Rate limits** are no longer published (shown only in AI Studio). The last published free-tier values for Gemma 3 were 30 requests/min, 15,000 tokens/min and 14,400 requests/day. At about 3k tokens per chunk plus the prompt, the token limit allows roughly 4-5 calls per minute. These numbers were not measured.

## Options considered

1. **OpenAI (ADR 0304's example).** Fast and reliable JSON mode, but a closed model. Paid, so it fits the task text worse.
2. **Gemma 4 on the Gemini API, OpenAI-compatible endpoint.** An open model and no code change, but slow, often 503 at measurement time, and it needs the `<thought>` strip.
3. **Gemma 4 on the Gemini API, native `generateContent`.** Documented for Gemma, but it needs a provider-specific adapter, which ADR 0304 rules out. Not needed, because option 2 works.
4. **Local Ollama only.** Fully on-premise, but `gemma3:4b` on CPU is slower still and weaker.

## Decision

Option 2. The hosted default is Gemma 4 on the Gemini API through its OpenAI-compatible endpoint:

```
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
LLM_MODEL=gemma-4-31b-it
LLM_API_KEY=<Gemini API key, only in .env>
```

The default model is `gemma-4-31b-it` (Damian, 2026-11-21). `gemma-4-26b-a4b-it` is the tested alternative to switch to, by `.env` only, when 31b keeps returning 503 "high demand". Measured on 2026-11-21:
- 31b: 3 of 3 calls returned 503 in the CLI run;
- 26b: 3 of 5 calls returned 200 in 15-30 s each, one returned 503 and one timed out at 60 s.

The circuit breaker's fall-back to rules-only stays the safety net for both.

For either model, the defaults must change: `LLM_TIMEOUT_S` 20 is below the measured latency. For the hosted Gemma, set `LLM_TIMEOUT_S=45` and `LLM_DOC_BUDGET_S=50`. Because the per-document budget must stay below the worker's claim idle time ([ADR 0310](0310-llm-chunking-and-budget.md)), also set `CLAIM_MIN_IDLE_MS=90000`.

- **OpenAI** stays a documented alternative: an `.env` change only.
- **Local Ollama Gemma (`gemma3:4b`, `--profile llm`)** stays the swap target.
- **503 and 429** count as `LlmUnavailable`: the circuit breaker opens and the documents fall back to rules-only. The Redis cache makes re-scans free ([ADR 0309](0309-llm-prompt-and-cache-contract.md)).

Rationale: the task text names Gemma 4, and the measured endpoint accepts exactly the request ADR 0309 defines. The only difference is the reasoning prefix, which a small, tested strip handles. The poor availability is absorbed by the paths that already exist (breaker, rules-only, cache).

## Default M2 threshold re-measured (successor note to ADR 0316)

Damian accepted on 2026-11-21 an M2 default threshold of **0.1**, down from 0.25. This change follows ADR 0316's procedure unchanged: the default is the best-F1 threshold of the rules-only gold run, written by `python analytics/eval/run.py --write-thresholds`. ADR 0316 itself is not edited.

- **Why it moved:** this change adds the M2 P0 rules R4, R6, R14, R17 and R18. On most gold documents they are `pass` or `not_applicable`, which adds weight to the score's denominator and lowers M2 scores.
- **Numbers:** rules-only run (no LLM), 69 gold documents; for M2, 23 positives and 12 negatives.
  - At 0.1: precision 0.933, recall 0.609, F1 0.737 (tp 14, fp 1, fn 9, tn 11).
  - At 0.25: precision 0.929, recall 0.565, F1 0.703 (tp 13, fp 1, fn 10, tn 11).
  - The F1 plateau is 0.05-0.1.
- **Where it is copied:** `analytics/eval/thresholds.json`, `analytics/src/investwatch_analytics/events.py` `DEFAULT_THRESHOLDS` and `api/src/investwatch_api/thresholds.py` `DEFAULTS`. `analytics/tests/test_eval_thresholds.py` pins all three.
- **Next measurement:** re-measured with the LLM (`run.py --llm`) after this change merges. LLM verdicts can move R3, R17 and R18, and with them the best threshold.

## Consequences

- **Data terms.** In the EEA, the Gemini API's paid-tier data-use terms apply even on the free quota: prompts and answers are not used to improve Google's products. This was relayed by the coordinating session from Google's terms and not re-checked by the agent. Scraped public web text and firm names leave the stack for Google's endpoint. This stays within the mentor exception of ADR 0304, and the hand-in README must say so.
- **The demo must not depend on the hosted model.** With the 503 rate seen, a live demo may run mostly rules-only. Pre-warm the cache before the demo by analysing the demo documents once, and keep the local Ollama profile ready.
- **Quota.** M3 makes its LLM call only when its rules already found a candidate (decision R60, follow-ups), and nothing is deferred on compliant pages. This keeps the number of calls low.
- **Small Gemma 4 for Ollama.** Google lists no hosted size below 26B. Whether a small Gemma 4 build exists for Ollama was not checked (follow-up). `gemma3:4b` stays the local swap target.
- `.env.example` and `analytics/compose.yaml` comments are updated in the same PR.
