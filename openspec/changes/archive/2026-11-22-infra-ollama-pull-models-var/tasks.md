## 1. Rename the pull list

- [x] 1.1 `infra/compose.yaml`: `ollama-pull` loops over `OLLAMA_PULL_MODELS`
- [x] 1.2 Smoke probe for a failed pull sets `OLLAMA_PULL_MODELS`
- [x] 1.3 `.env.example`, `infra/README.md`, root `README.md`, `analytics/README.md`
- [x] 1.4 Mutation check. mutations: n/a, config only; verified by a real pull instead (task 2.1)

## 2. Close

- [x] 2.1 Real run on the demo machine (issue #74 rehearsal): with the old name `ollama-pull` exits 1 with `mkdir gemma3:4b bge-m3: read-only file system`; with `OLLAMA_PULL_MODELS` it pulls `gemma3:4b` and `bge-m3` and exits 0
- [x] 2.2 Status row, AI log row, `docs-check`
