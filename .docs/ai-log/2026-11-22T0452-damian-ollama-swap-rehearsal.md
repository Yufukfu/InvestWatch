---
when: Sun 04:52
who: Damian
---

## What was done with AI

A Claude Code side session of the issue coordination rehearsed the hosted-to-Ollama swap from the `analytics/README.md` runbook (PR #69) on the demo machine for issue #74. It ran its own stack, switched from hosted to local and back, replayed documents through `iw:documents`, timed every step and corrected the runbook from what it saw. It also fixed `ollama-pull` in the OpenSpec change `infra-ollama-pull-models-var`.

## Outcome / lesson

The rehearsal found that `ollama-pull` had never pulled anything: its model list was in `OLLAMA_MODELS`, which Ollama reads as its storage directory, and `docker compose up ollama-pull` still exits 0 when it fails. The #65 change was merged with its models not pulled, so a real pull would have caught it. On CPU, `gemma3:4b` needs 182 s for one short M1 check (4.6 s hosted); the runbook's 120 s timeout was a guess and every local call timed out with it. A Docker Desktop crash during the pull, with several stacks running, also cost time. Lesson: rehearse a runbook on the real machine before it goes on a slide, and run one stack at a time with the `llm` profile.
