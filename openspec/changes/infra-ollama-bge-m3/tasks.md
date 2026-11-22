## 1. Pull and serve bge-m3

- [x] 1.1 Smoke test first: with `SMOKE_LLM=1`, `/v1/models` must list `bge-m3` as well as `gemma3:4b`, and the failed-pull probe sets `OLLAMA_MODELS`
- [x] 1.2 `infra/compose.yaml`: `ollama-pull` loops over `OLLAMA_MODELS`; `ollama` gets `OLLAMA_MAX_LOADED_MODELS` and `OLLAMA_KEEP_ALIVE`
- [x] 1.3 `.env.example`, `infra/README.md`, `analytics/README.md`
- [x] 1.4 Mutation check. mutations: n/a, config only; the model-serving probe needs `SMOKE_LLM=1` (several GB), not run

## 2. Close

- [x] 2.1 `docker compose -f infra/compose.yaml --profile llm config` resolves the three values; `infra/tests/smoke.sh` passes without `SMOKE_LLM`
- [x] 2.2 Status row, AI log row, `docs-check`
