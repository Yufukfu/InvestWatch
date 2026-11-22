---
when: Sat ~19:00 → Sun ~01:00
who: Damian
---

## What was done with AI

A Claude Code side session proposed `analytics-llm-p0` (stage 2), revised it to the ZASÓB criteria the coordinating session read out, and applied it per task group (failing test first, a mutation check with a backup-and-restore script, a read-only reviewer per group with `focus: security` on the LLM groups). It covered the M2 P0 rules R4, R6, R14, R17 and R18, and the LLM layer (OpenAI-compatible httpx client, delimited prompt, chunking, verified quotes, Redis cache, budget, breaker), wired into the worker, the CLI and M1/M3 after #35 merged. Task 12.4 ran once against hosted Gemma 4 on the Gemini API (ADR 0317).

## Outcome / lesson

Reviewers caught what tests missed: regex false positives (`Rada Nadzorcza`, an amount after a preposition read as a year), a slow-drip server outliving the timeout, look-alike `</document>` tags, chunks advancing one sentence at a time, untested `re.escape`, and a recorded "18/18" that had three survivors. The live run found what no stub could: Gemma 4 prefixes JSON answers with `<thought>…</thought>`, half the calls returned 503, and latency was 15-60 s. Lessons: `iw-reviewer` is not registered outside the repo, so a general-purpose agent following its file stood in. A per-commit rebase over a moved YAML file silently damaged it, so later syncs used one merge. Hostile-input timing tests and absolute limits drift as rules are added.
