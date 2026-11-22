---
when: Sun ~01:30
who: Damian
---

## What was done with AI

The analytics coordinating Claude Code session wrote the runbook for switching the LLM between hosted Gemma 4 (Gemini API) and local `gemma3:4b` through Ollama, from the merged `analytics-llm-p0` code and ADRs 0304/0317, after checking each claim against `config.py` (`_LOCAL_HOSTS`, the budget check) and `compose.yaml`

## Outcome / lesson

Docs only (`analytics/README.md`, `.docs/INDEX.md`). The local timeouts are estimates: `gemma3:4b` speed on the team's laptops is still unmeasured, and the README says so
