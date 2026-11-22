## 1. Rename the pull list

- [x] 1.1 Smoke test first: `llm_pull_env` checks, from `docker compose --profile llm config` with a stale `OLLAMA_MODELS` exported, that `ollama-pull` has `OLLAMA_PULL_MODELS` and neither container has `OLLAMA_MODELS`; the failed-pull probe sets `OLLAMA_PULL_MODELS`
- [x] 1.2 `infra/compose.yaml`: `ollama-pull` maps and loops over `OLLAMA_PULL_MODELS`
- [x] 1.3 `.env.example`, `infra/README.md`, `analytics/README.md`, `README.md`
- [x] 1.4 Mutation check: `llm_pull_env` against the `origin/main` compose is red (`OLLAMA_MODELS` in the `ollama-pull` environment), green against the fix

## 2. Close

- [x] 2.1 Live proof on a fresh volume in a throwaway project (`iw-fix149`, only `ollama-pull`, `OLLAMA_PULL_MODELS=bge-m3`, stale `OLLAMA_MODELS="gemma3:4b bge-m3"` exported): exit 0; project and volume removed afterwards
- [x] 2.2 AI log row, `docs-check`, `openspec validate --all --strict`
