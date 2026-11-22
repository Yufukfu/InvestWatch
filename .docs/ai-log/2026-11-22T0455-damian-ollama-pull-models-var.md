---
when: Sun ~04:55
who: Damian
---

## What was done with AI

A Claude Code side session fixed issue #149: the pull list `OLLAMA_MODELS` from #86 is also Ollama's own models-directory setting, so on a fresh volume `ollama serve` in `ollama-pull` tried to `mkdir` the list in the read-only root and the pull exited 1. Renamed to `OLLAMA_PULL_MODELS` through the OpenSpec change `infra-ollama-pull-models-var`, with a `config`-level smoke check that needs no download

## Outcome / lesson

Branch `infra/ollama-pull-models-var`, reviewed by Kacper (infra owner). The smoke check is red on the old compose, green on the fix; a live pull of only `bge-m3` on an empty volume in a throwaway project exited 0 with a stale `OLLAMA_MODELS` exported. Lesson: before naming a variable after a tool, check the tool's own environment settings. The old failed-pull smoke probe passed for the wrong reason (the mkdir error, not the unknown model).
