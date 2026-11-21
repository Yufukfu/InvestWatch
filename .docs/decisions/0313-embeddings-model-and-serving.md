# 0313. Embeddings model and serving

- Status: accepted
- Date: 2026-11-21
- Deciders: agent-written for Damian (change `analytics-embeddings`, stage 3); accepted by Damian via the PR of that change

## Context

`doc/Opis Wyzwania HackNation UKNF 19.11.pdf` p.2 lists embeddings among the preprocessing steps. §5 asks for free, on-premise models and no external paid APIs. The jury gives 20% of the score to fit with the specification. `.docs/analytics-plan.md` §1.5 names `bge-m3` or `multilingual-e5`, and §7 uses embeddings for the topic gate and for grouping. [ADR 0304](0304-llm-serving.md) makes the LLM hosted by default under a mentor exception, with local Gemma on the optional `ollama` service (compose profile `llm`) as the swap target, reached through the OpenAI-compatible `/v1` API. `finding.schema.json` v1 already has `model.embedder`.

## Options considered

1. **`bge-m3` on the local `ollama` service through `/v1/embeddings`.**
   - Open weights, MIT licence, multilingual including Polish, 1024 dimensions, up to 8192 input tokens. It is published in the Ollama library as `bge-m3` (about 1.2 GB).
   - It reuses the service and the API style ADR 0304 already set up, so no new container is needed.
2. **`multilingual-e5-large`.**
   - It is also open, with 1024 dimensions.
   - It needs `query:` / `passage:` input prefixes and takes 512 input tokens.
   - It is not in the official Ollama library, so it would need a custom import or a second server (for example TEI).
3. **A hosted embeddings API** (for example OpenAI `text-embedding-3-small`). This is a paid external API, which §5 excludes. The ADR 0304 mentor exception covers only the LLM.
4. **In-process `sentence-transformers`.** No HTTP hop, but it adds `torch` (hundreds of MB) to the analytics image and loads the model in every worker container.

## Decision

Option 1. Analytics calls the OpenAI-compatible `POST {EMBED_BASE_URL}/embeddings` with plain `httpx`, configured by env only (`EMBED_BASE_URL`, `EMBED_MODEL=bge-m3`, `EMBED_API_KEY`, `EMBED_DIM=1024`, timeouts and limits). The documented values point to `http://ollama:11434/v1`. Unlike the LLM, there is no hosted default: the documented configuration is local only (evidence: PDF §5; the ADR 0304 exception is scoped to the LLM).

With `EMBED_BASE_URL` empty, or the model unreachable, the pipeline runs without vectors and records `model.embedder = null` (degrade-don't-fail, `analytics/CLAUDE.md`).

Why option 1: it is the plan's first choice, it works out of the box on Polish without prompt prefixes, and it needs no new service or heavy dependency. It also keeps the same env-only swap path as the LLM, so any OpenAI-compatible embeddings server can replace it.

## Consequences

- A plain `docker compose up` (no `llm` profile) runs with embeddings off. The topic gate then uses its dictionary only. This is a supported, documented state.
- Infra asks (Kacper, `infra/`):
  - `ollama-pull` also pulls `bge-m3`;
  - `OLLAMA_MAX_LOADED_MODELS=2`, so Gemma and `bge-m3` don't evict each other;
  - a demo-length `OLLAMA_KEEP_ALIVE`;
  - the infra spec scenario updated.

  This relates to issue #32. Until then, `bge-m3` is pulled by hand.
- Input is cut to `EMBED_MAX_CHARS` (4000), so the embedder does not depend on the server's context length.
- Vectors are cached in Redis by `content_hash` + model variant. A model swap misses the cache by construction, and the gate threshold is re-calibrated on the gold set after a swap (plan §8).
- Revisit if the gold set shows `bge-m3` similarity does not separate the gate fixtures. The fallback is `multilingual-e5` through a second OpenAI-compatible server, which is an env change.
