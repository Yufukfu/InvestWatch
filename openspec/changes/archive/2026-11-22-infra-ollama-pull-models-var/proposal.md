# Proposal

## Why

`OLLAMA_MODELS`, the pull list `ollama-pull` got in `infra-ollama-bge-m3`, is also Ollama's own setting for the models **directory**. On a fresh volume `ollama serve` inside `ollama-pull` treats the list as a relative path, fails with `mkdir bge-m3: read-only file system`, and the pull exits 1, so neither `gemma3:4b` nor `bge-m3` is pulled. Stacks whose volume already holds the models do not notice. Issue #149.

## What Changes

- The pull list is renamed `OLLAMA_PULL_MODELS` (same default, `gemma3:4b bge-m3`). Neither `ollama` nor `ollama-pull` maps `OLLAMA_MODELS`, so `ollama serve` keeps its default `/root/.ollama/models`.
- A stale `OLLAMA_MODELS` list in an old `.env` is ignored: compose passes only what the file maps. `.env.example` says so.
- `.env.example`, `infra/README.md`, `analytics/README.md`, the root README config table and the smoke test follow. The smoke test gains a `config` check that runs without any model download.

**Out of scope:** the models themselves, memory limits, networks. `infra/` is owned by Kacper (ADR 0202), who reviews; Damian makes the fix because #86 (his) introduced the name.

Touches no contract, REST route or event.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `shared-infrastructure`: the pull list is `OLLAMA_PULL_MODELS`, and no `ollama` container gets `OLLAMA_MODELS`.

## Impact

- Code: `infra/compose.yaml`, `infra/tests/smoke.sh`, `.env.example`.
- Docs: `infra/README.md`, `analytics/README.md`, `README.md`.
- An existing `.env` with `OLLAMA_MODELS="gemma3:4b bge-m3"` keeps working with the default list; a custom list must be renamed to keep it.
