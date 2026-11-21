# 0310. LLM chunking and the per-document budget

- Status: accepted
- Date: 2026-11-21
- Deciders: agent-written (change `analytics-llm-p0`, stage 2); accepted by Damian via the PR that applies `analytics-llm-p0`

## Context

`.docs/analytics-plan.md` §7 asks for "a length limit (chunks of ~3k tokens, result = worst chunk)", but does not say how to split, how many chunks to send, or what happens when one chunk fails. Three facts constrain the answer:

- **The model.** [ADR 0304](0304-llm-serving.md) makes local `gemma3:4b` on Ollama `/v1` the swap target. That endpoint takes only OpenAI-compatible parameters, so `num_ctx` cannot be set per request, and the server's default context window applies. In Ollama that default is a few thousand tokens, and the server-wide `OLLAMA_CONTEXT_LENGTH` variable raises it. The exact default depends on the Ollama version and is to be verified on the infra smoke run (`infra/tests/smoke.sh`, `SMOKE_LLM=1`). Ollama shortens a prompt that is longer than the window, which would silently cut the text being judged.
- **The worker.** `analytics-worker` processes one message at a time, synchronously. It XAUTOCLAIMs messages idle longer than `CLAIM_MIN_IDLE_MS` (default 60000) (`openspec/changes/analytics-worker/design.md`, decisions 1 and 6). A document whose LLM calls take longer than that is handed to a second consumer while it is still being processed. The upsert makes that harmless, but it doubles the LLM cost.
- **The rules.** R3 looks for a warning within ±2 sentences of a claim (`m2_rules.yaml` `window: 2`), and the LLM judges R3 only for warnings just outside that window, so a chunk border must not separate a claim from its warning.

## Options considered

1. **Send the whole text, one call per module.** This is the simplest option. On Ollama a long page exceeds the default window and is shortened without an error. On hosted models it costs more on long legal pages, and one slow call can exceed the claim idle time.
2. **Fixed-size character chunks with no overlap.** This is easy, but it cuts mid-sentence. A claim and its warning can fall in different chunks, and a quote can straddle a border and then fail verification.
3. **Chunks on sentence boundaries with a 4-sentence overlap, a cap on the number of chunks, worst chunk wins, and a per-document wall-clock budget below the claim idle time.** The overlap covers R3's ±2 window plus the 2-sentence borderline margin in which the LLM judges R3. The cap and the budget bound the latency. A single unusually long sentence is cut at the limit.

For a chunk that fails: taking the worst of the chunks that did succeed biases the result toward `pass`, because the missing chunk may hold the `fail`. Dropping the module's LLM verdicts falls back to the rules-only result, which is already the defined degradation path ([ADR 0309](0309-llm-prompt-and-cache-contract.md)).

## Decision

Option 3:

- **Chunk size and split:** `LLM_CHUNK_CHARS`, 9000 by default (about 3k tokens of Polish), split on `pre.sentences`, with consecutive chunks overlapping by up to 4 sentences (R3 `window` plus `borderline_margin`), capped at half a chunk; every chunk ends later than the previous one. A single longer sentence is cut at the limit.
- **Chunk cap:** `LLM_MAX_CHUNKS`, 4 by default. Text beyond the cap is not sent, the log says `llm_truncated`, and the rules still cover the full text.
- **Merge:** per check, worst chunk wins (`fail` > `uncertain` > `pass` > `not_applicable`), and ties go to the earliest chunk. If any chunk of a module's call fails, all of that module's LLM verdicts are dropped.
- **Timeouts and budget:**
  - `LLM_TIMEOUT_S`: the read timeout per request, 20 by default; the connect timeout is 3 s.
  - `LLM_DOC_BUDGET_S`: the wall clock per document across modules and chunks, 40 by default. When it runs out, the remaining calls are skipped as `llm_budget_exhausted`.
  - Config validation requires `LLM_DOC_BUDGET_S * 1000 < CLAIM_MIN_IDLE_MS`.
- **Circuit breaker:** after `LLM_BREAKER_FAILURES` (3) consecutive unavailable outcomes, the judge stops calling for `LLM_BREAKER_COOLDOWN_S` (60). After that, one call is tried again (half-open).
- **Ollama context window:** infra sets `OLLAMA_CONTEXT_LENGTH=8192` on the `ollama` service (requested from Kacper through the change proposal). A chunk of about 3k tokens, a system prompt of about 1k tokens and the answer fit in it.

Rationale: the Ollama `/v1` limitation means option 1 can lose text silently on the swap target that ADR 0304 obliges us to keep working. R3's ±2-sentence window plus its 2-sentence borderline margin is the reason for a 4-sentence overlap, rather than an arbitrary character overlap. The worker's 60 s claim idle time is the reason the budget must stay below it. Dropping a module's verdicts on a partial failure reuses the single degradation path instead of inventing a biased partial merge.

## Consequences

- Most marketing pages are well under 9000 characters, and they cost exactly one call per module that has deferred checks.
- A long legal page is judged on its first four chunks only by the LLM. The rules still see all of it, and the log records the truncation.
- With a dead endpoint, a document costs at most one timeout until the breaker opens, and then nothing for the cooldown.
- If the infra smoke run shows a larger Ollama default, or the gold set shows that smaller chunks judge better, `LLM_CHUNK_CHARS` changes by env. This ADR is superseded only if the split strategy itself changes.
- With very long sentences a fixed 4-sentence overlap would advance by one sentence per request, so four chunks would cover only about a quarter of a long page; the half-chunk cap keeps the advance at about half a chunk (found in the group 6 review of `analytics-llm-p0`).
- `.docs/analytics-plan.md` §7 is updated in the same PR with these defaults.
