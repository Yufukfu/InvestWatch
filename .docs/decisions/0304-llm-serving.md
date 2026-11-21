# 0304. How Gemma is served to analytics

- Status: proposed
- Date: 2026-11-21
- Deciders: A, B, C (to be confirmed)

## Context

The team sync decided on Gemma accessed through an HTTP API ([integration-plan.md](../integration-plan.md), team sync decisions). Analytics calls it through an Ollama-compatible endpoint configured by env (`LLM_BASE_URL`, `LLM_MODEL`, optional `LLM_API_KEY`) and must degrade to rules-only when it is unreachable ([`analytics/CLAUDE.md`](../../analytics/CLAUDE.md), [analytics-plan.md](../analytics-plan.md) §7).

The UKNF task (`doc/Opis Wyzwania HackNation UKNF 19.11.pdf`, section 5) requires an open-source, on-premise stack: free AI models (Ollama, vLLM named as examples) and no external paid APIs; the whole stack starts on-premise with one command. "Compliance with the specification and preferred technologies" is 20% of the score and the jury reviews the libraries used.

Not measured yet: tokens per second of `gemma3:4b` / `gemma3:12b` on the team's laptops (CPU and any GPU). That number decides whether one call per document and module fits the 30 s budget for the demo.

## Options considered

1. **Local Ollama container in `docker compose`, model pulled at start-up.** Fully on-premise and reproducible, the strongest match to the task text. On CPU only small models are practical (for example `gemma3:4b`); the first start downloads the weights (several GB), so they should be pre-pulled before the demo.
2. **Ollama on one teammate's GPU machine during development, local container for the final demo.** Faster iteration on prompts with a larger model; analytics only changes `LLM_BASE_URL`. Prompt quality tuned on a large model may drop on the small demo model, so the gold-set evaluation ([analytics-plan.md](../analytics-plan.md) §8) has to be re-run on the demo model.
3. **Hosted Gemma API (a cloud provider serving the open weights).** No local hardware limits and the best latency. The stack is no longer on-premise and depends on an external service at runtime, which conflicts with the task requirements; usable at most as an optional development endpoint, never as the only one.

## Decision

_To be written by the team (A, B, C)._

## Consequences

_To be written together with the decision._
