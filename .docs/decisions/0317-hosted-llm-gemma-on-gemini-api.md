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
LLM_MODEL=gemma-4-26b-a4b-it   # measured ~9.5 s per call; gemma-4-31b-it measured ~57 s
LLM_API_KEY=<Gemini API key, only in .env>
```

Damian named `gemma-4-31b-it` in the team `.env`. This ADR records that the measured latency of `gemma-4-26b-a4b-it` was about six times lower. The choice between the two stays an `.env` value.

For either model, the defaults must change: `LLM_TIMEOUT_S` 20 is below the measured latency. For the hosted Gemma, set `LLM_TIMEOUT_S=45` and `LLM_DOC_BUDGET_S=50`. Because the per-document budget must stay below the worker's claim idle time ([ADR 0310](0310-llm-chunking-and-budget.md)), also set `CLAIM_MIN_IDLE_MS=90000`.

- **OpenAI** stays a documented alternative: an `.env` change only.
- **Local Ollama Gemma (`gemma3:4b`, `--profile llm`)** stays the swap target.
- **503 and 429** count as `LlmUnavailable`: the circuit breaker opens and the documents fall back to rules-only. The Redis cache makes re-scans free ([ADR 0309](0309-llm-prompt-and-cache-contract.md)).

Rationale: the task text names Gemma 4, and the measured endpoint accepts exactly the request ADR 0309 defines. The only difference is the reasoning prefix, which a small, tested strip handles. The poor availability is absorbed by the paths that already exist (breaker, rules-only, cache).

## Consequences

- **Data terms.** In the EEA, the Gemini API's paid-tier data-use terms apply even on the free quota: prompts and answers are not used to improve Google's products. This was relayed by the coordinating session from Google's terms and not re-checked by the agent. Scraped public web text and firm names leave the stack for Google's endpoint. This stays within the mentor exception of ADR 0304, and the hand-in README must say so.
- **The demo must not depend on the hosted model.** With the 503 rate seen, a live demo may run mostly rules-only. Pre-warm the cache before the demo by analysing the demo documents once, and keep the local Ollama profile ready.
- **Quota.** M3 makes its LLM call only when its rules already found a candidate (decision R60, follow-ups), and nothing is deferred on compliant pages. This keeps the number of calls low.
- **Small Gemma 4 for Ollama.** Google lists no hosted size below 26B. Whether a small Gemma 4 build exists for Ollama was not checked (follow-up). `gemma3:4b` stays the local swap target.
- `.env.example` and `analytics/compose.yaml` comments are updated in the same PR.
