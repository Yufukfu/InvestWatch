# 0304. How Gemma is served to analytics

- Status: accepted
- Date: 2026-11-21
- Deciders: agent-written from Damian's choices; accepted by: pending approval of PR #3

## Context

The team sync decided on Gemma accessed through an HTTP API ([integration-plan.md](../integration-plan.md), team sync decisions). Analytics calls it through an Ollama-compatible endpoint configured by env (`LLM_BASE_URL`, `LLM_MODEL`, optional `LLM_API_KEY`) and must degrade to rules-only when it is unreachable ([`analytics/CLAUDE.md`](../../analytics/CLAUDE.md), [analytics-plan.md](../analytics-plan.md) §7).

The UKNF task (`doc/Opis Wyzwania HackNation UKNF 19.11.pdf`, section 5) requires an open-source, on-premise stack: free AI models (Ollama, vLLM named as examples) and no external paid APIs; the whole stack starts on-premise with one command. "Compliance with the specification and preferred technologies" is 20% of the score and the jury reviews the libraries used.

Not measured yet: tokens per second of `gemma3:4b` / `gemma3:12b` on the team's laptops (CPU and any GPU). That number decides whether one call per document and module fits the 30 s budget for the demo.

## Options considered

1. **Local Ollama container in `docker compose`, model pulled at start-up.** Fully on-premise and reproducible, the strongest match to the task text. On CPU only small models are practical (for example `gemma3:4b`); the first start downloads the weights (several GB), so they should be pre-pulled before the demo.
2. **Ollama on one teammate's GPU machine during development, local container for the final demo.** Faster iteration on prompts with a larger model; analytics only changes `LLM_BASE_URL`. Prompt quality tuned on a large model may drop on the small demo model, so the gold-set evaluation ([analytics-plan.md](../analytics-plan.md) §8) has to be re-run on the demo model.
3. **Hosted Gemma API (a cloud provider serving the open weights).** No local hardware limits and the best latency. The stack is no longer on-premise and depends on an external service at runtime, which conflicts with the task requirements; usable at most as an optional development endpoint, never as the only one.

## Decision

None of the three options as written: **analytics uses a hosted model during the hackathon, through an OpenAI-compatible chat completions endpoint (for example OpenAI), and keeps a local open model as a drop-in fallback.**

- Local fallback: an optional `ollama` service in `docker compose` (behind a compose profile, so a plain `docker compose up` does not download weights) serving `gemma3:4b`.
- Swap: analytics speaks only the OpenAI-compatible API, which Ollama also serves under `/v1`. Moving between a hosted provider and local Gemma changes `LLM_BASE_URL`, `LLM_MODEL` and `LLM_API_KEY` only, with no code change and no provider-specific SDK.

Evidence: the HackNation UKNF challenge mentors told the team on 2026-11-21 that a hosted provider such as OpenAI is fine for the hackathon scope, as long as the codebase makes it easy to swap to open-source models (Gemma or others) later (relayed by Adam in a PR #3 comment). Section 5 of the task PDF still says free models only and no external paid APIs, so this is a **mentor exception**, not something the PDF states.

Why (Damian): a hosted model is acceptable only if it can be replaced by another hosted or a local model easily, which is also the mentors' condition.

## Consequences

- No local hardware limits during development; the unmeasured tokens per second of local Gemma matters only for the fallback.
- The jury still reads the PDF requirement: the hand-in README and the demo must name the mentor exception and show the local fallback (`gemma3:4b` through the compose profile), otherwise "compliance with the specification" (20%) may lose points.
- No provider-specific features: prompts use only what both a hosted OpenAI-compatible endpoint and Ollama `/v1` support (chat messages, `temperature`, JSON response format). Prompts are tested on both backends before the demo.
- Runtime depends on an external service: the rules-only fallback ([analytics-plan.md](../analytics-plan.md) §7) covers an unreachable endpoint or a missing key; `LLM_API_KEY` lives only in `.env`.
- The gold-set evaluation ([analytics-plan.md](../analytics-plan.md) §8) is re-run after any model swap.
- Docs updated in this PR: root `CLAUDE.md` (on-premise line), [`analytics/CLAUDE.md`](../../analytics/CLAUDE.md) (LLM line), [integration-plan.md](../integration-plan.md) §1 and §7, [analytics-plan.md](../analytics-plan.md) §1, §7 and risks. The `ollama` compose profile is added by Damian together with `docker-compose.yml`.
