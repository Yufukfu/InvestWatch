---
when: Sun 06:05
who: Kacper
---

## What was done with AI

A Claude Code session reviewed the root `README.md` against the brief's "Dokumentacja techniczna" line (Quick Start, hardware, service configuration, no AI slop), then rewrote it. The prompt asked whether the text read as robotic. Before editing, the session checked each Quick Start claim against `scripts/init-env.sh`, `.env.example`, the compose files and `analytics/README.md`, and diffed every `${VAR}` in the compose files against the variables named in the README.

## Outcome / lesson

The text was dense rather than fluffy. It had a commit hash in the hardware section, many "X: link" pointers, nested parentheses, and internal notes (CODEOWNERS, "drafts, contracts not yet confirmed", a `doc/` row for a folder removed before hand-in). The check also found three factual problems. The README called the hosted LLM the default, but `init-env.sh` leaves `LLM_*` empty, so a jury run would get rules only without being told. The configuration table had drifted: it was missing `GATE_EMBED_MIN_MARGIN`, `GATE_EMBED_MIN_CHARS`, `X_AUTH_TOKEN`, `X_CT0`, `YT_TRANSCRIPT_PROXY` and `YOUTUBE_MAX_VIDEOS`, and still listed the removed `GATE_SIM_THRESHOLD`. It also gave `analytics-eval` the whole LLM set, although that service gets only `POSTGRES_*` and `LOG_LEVEL`. Issue #75 asked for every variable per service, so the full list stays, split into rows by purpose. The `api/` folder was missing from the structure table. Lesson: a hand-written list of env vars drifts within hours, so diff it against the compose files before hand-in, not by reading it.
