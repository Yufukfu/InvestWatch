## 1. Pull and serve bge-m3

- [x] 1.1 Smoke test first: with `SMOKE_LLM=1`, `/v1/models` must list `bge-m3` as well as `gemma3:4b`, and the failed-pull probe sets `OLLAMA_MODELS`
- [x] 1.2 `infra/compose.yaml`: `ollama-pull` loops over `OLLAMA_MODELS`; `ollama` gets `OLLAMA_MAX_LOADED_MODELS` and `OLLAMA_KEEP_ALIVE`
- [x] 1.3 `.env.example`, `infra/README.md`, `analytics/README.md`
- [x] 1.4 Mutation check. mutations: n/a, config only; the model-serving probe needs `SMOKE_LLM=1` (several GB), not run

## 2. Close

- [x] 2.1 `docker compose -f infra/compose.yaml --profile llm config` resolves the three values, with and without the `.env.example` lines; `infra/tests/smoke.sh` without `SMOKE_LLM`: every `llm` check passes, 36 passed and 3 failed overall. The 3 failures are in the `parallel` and `dev-ports` groups and were caused by other stacks running on the same machine (gateway port `127.0.0.1:18080` already allocated, Postgres unhealthy under load), not by this change
- [x] 2.2 Status row, AI log row, `docs-check`
