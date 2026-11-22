# Proposal

## Why

`analytics-embeddings` (ADR 0313) calls a local `bge-m3` model through Ollama's OpenAI-compatible `/v1/embeddings`, with no hosted fallback (the ADR 0304 exception covers the LLM only). The `llm` profile pulls only `gemma3:4b`, and with Ollama's defaults the two models would evict each other on every document. Issue #65.

## What Changes

- `ollama-pull` pulls every model in `OLLAMA_MODELS` (space-separated, default `gemma3:4b bge-m3`) and exits non-zero on the first failure. It replaces the single-model `OLLAMA_MODEL`.
- `ollama` gets `OLLAMA_MAX_LOADED_MODELS` (default `2`) and `OLLAMA_KEEP_ALIVE` (default `30m`).
- `.env.example`, `infra/README.md`, `analytics/README.md` and the smoke test follow.

**Out of scope:** the embeddings code in analytics, the networks (analytics already reaches `ollama` on `data`), memory limits. `infra/` is owned by Kacper (ADR 0202); Damian makes this change because it goes with the analytics LLM layer, as for #32.

Touches no contract, REST route or event.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `shared-infrastructure`: the `llm` profile also serves `bge-m3`.

## Impact

- Code: `infra/compose.yaml`, `infra/tests/smoke.sh`, `.env.example`.
- Docs: `infra/README.md`, `analytics/README.md`, `.docs/status/platform.md`, `.docs/ai-workflow.md`.
- An existing `.env` with `OLLAMA_MODEL` keeps working: the variable is ignored and the default list is pulled.
