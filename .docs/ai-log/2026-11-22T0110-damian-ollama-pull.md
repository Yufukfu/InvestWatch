---
when: Sun ~01:10
who: Damian
---

## What was done with AI

A Claude Code side session of the analytics coordination implemented issue #65: `ollama-pull` loops over `OLLAMA_MODELS` (default `gemma3:4b bge-m3`), `ollama` gets `OLLAMA_MAX_LOADED_MODELS=2` and `OLLAMA_KEEP_ALIVE=30m`, through the OpenSpec change `infra-ollama-bge-m3`

## Outcome / lesson

Branch `infra/ollama-pull-bge-m3`. It also found that the issue's manual fallback (`docker compose exec ollama ollama pull bge-m3`) cannot work, because the serving `ollama` is on the internal `data` network only; the README says to rerun `ollama-pull` instead. Models not pulled.
