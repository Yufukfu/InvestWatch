---
when: Sat ~21:20
who: Damian
---

## What was done with AI

Had Claude Code close issue #32: `OLLAMA_CONTEXT_LENGTH: ${OLLAMA_CONTEXT_LENGTH:-8192}` on the `ollama` service, a line in `.env.example` and a sentence in `infra/README.md`, then checked with `docker compose --profile llm config` that it resolves to 8192 with and without the `.env` line and that a plain `up` still starts no Ollama

## Outcome / lesson

Config only, no new OpenSpec change: the hook's spec rule covers service directories, not `infra/`. The archived follow-up row was marked done in place, as an earlier commit (9b0fb3a) had already edited an archived `follow-ups.md`
