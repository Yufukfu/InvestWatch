# Proposal

## Why

The issue #74 rehearsal of the hosted-to-Ollama swap found that `ollama-pull` never pulls anything on `main`. It passes the model list in `OLLAMA_MODELS`, but Ollama reads `OLLAMA_MODELS` as its model storage directory. `ollama serve` inside the one-shot fails with `mkdir gemma3:4b bge-m3: read-only file system`, the wait loop gives up and the container exits 1. `docker compose up ollama-pull` still returns 0, so the failure is easy to miss. The bug came with `infra-ollama-bge-m3` (issue #65). The smoke probe for a failed pull passed for the wrong reason: it also set `OLLAMA_MODELS`, so the server failed before any pull.

## What Changes

- `ollama-pull` reads its model list from `OLLAMA_PULL_MODELS` (same default, `gemma3:4b bge-m3`). `OLLAMA_MODELS` is left to Ollama.
- `.env.example`, `infra/README.md`, the root `README.md` configuration table, `analytics/README.md` (runbook) and the smoke probe follow.

**Out of scope:** the serving `ollama` service, the networks, the limits.

Touches no contract, REST route or event.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `shared-infrastructure`: the pull list variable is `OLLAMA_PULL_MODELS`.

## Impact

- Code: `infra/compose.yaml`, `infra/tests/smoke.sh`, `.env.example`.
- An existing `.env` with `OLLAMA_MODELS` keeps working: compose no longer reads it and the default list is pulled. A custom list must be renamed to `OLLAMA_PULL_MODELS`.
