# 0304. How Gemma is served to analytics

- Status: accepted
- Date: 2026-11-21
- Deciders: agent-written from C's choices; accepted by A, B and C via PR #3

## Context

The team sync decided on Gemma accessed through an HTTP API ([integration-plan.md](../integration-plan.md), team sync decisions). Analytics calls it through an Ollama-compatible endpoint configured by env (`LLM_BASE_URL`, `LLM_MODEL`, optional `LLM_API_KEY`) and must degrade to rules-only when it is unreachable ([`analytics/CLAUDE.md`](../../analytics/CLAUDE.md), [analytics-plan.md](../analytics-plan.md) §7).

The UKNF task (`doc/Opis Wyzwania HackNation UKNF 19.11.pdf`, section 5) requires an open-source, on-premise stack: free AI models (Ollama, vLLM named as examples) and no external paid APIs; the whole stack starts on-premise with one command. "Compliance with the specification and preferred technologies" is 20% of the score and the jury reviews the libraries used.

Not measured yet: tokens per second of `gemma3:4b` / `gemma3:12b` on the team's laptops (CPU and any GPU). That number decides whether one call per document and module fits the 30 s budget for the demo.

## Options considered

1. **Local Ollama container in `docker compose`, model pulled at start-up.** Fully on-premise and reproducible, the strongest match to the task text. On CPU only small models are practical (for example `gemma3:4b`); the first start downloads the weights (several GB), so they should be pre-pulled before the demo.
2. **Ollama on one teammate's GPU machine during development, local container for the final demo.** Faster iteration on prompts with a larger model; analytics only changes `LLM_BASE_URL`. Prompt quality tuned on a large model may drop on the small demo model, so the gold-set evaluation ([analytics-plan.md](../analytics-plan.md) §8) has to be re-run on the demo model.
3. **Hosted Gemma API (a cloud provider serving the open weights).** No local hardware limits and the best latency. The stack is no longer on-premise and depends on an external service at runtime, which conflicts with the task requirements; usable at most as an optional development endpoint, never as the only one.

## Decision

None of the three options as written: **analytics uses a cloud-hosted model, on the condition that it is easy to swap for another cloud or local model.** The model is reached only through the env configuration (`LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`), so switching provider or moving to a local Ollama container is a configuration change, not a code change.

Why (C): a cloud model is acceptable only if it can be replaced by another cloud or local model easily.

## Consequences

- No local hardware limits during development; the unmeasured tokens-per-second of local Gemma stops blocking work.
- Conflicts with the UKNF task (section 5: on-premise, free models, no external paid APIs, whole stack started with one command) and with "no paid APIs" in [`analytics/CLAUDE.md`](../../analytics/CLAUDE.md). This costs points in "compliance with the specification" (20%) unless the demo runs on a local model; the team has to decide that before the demo, and `analytics/CLAUDE.md` must be updated right after this ADR takes effect (PR #3 merges).
- The LLM client in analytics must not depend on one provider's API: either the chosen cloud endpoint is Ollama-compatible, or analytics gets a thin client layer covering both that provider and Ollama. Prompts are tested on at least two backends.
- Runtime depends on an external service: the rules-only fallback ([analytics-plan.md](../analytics-plan.md) §7) has to work when the endpoint is unreachable or the API key is missing; `LLM_API_KEY` stays out of the repository.
- The gold-set evaluation ([analytics-plan.md](../analytics-plan.md) §8) has to be re-run after any model swap.
