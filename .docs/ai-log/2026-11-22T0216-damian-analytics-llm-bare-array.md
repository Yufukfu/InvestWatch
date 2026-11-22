---
when: Sun ~02:00
who: Damian
---

## What was done with AI

A Claude Code side session applied `analytics-llm-bare-array` at the coordinator's request, after the #92 evaluation. It confirmed the cause before writing code: a debug run saved only the message content of each LLM reply, never the request, headers or key. 5 of 8 `gemma-4-26b-a4b-it` replies were bare result arrays. The work then ran test-first, with a scripted mutation check and a subagent review (`security: yes`).

## Outcome / lesson

The cause was checked, not guessed. Two mutants survived the first run (a scalar wrapped like an array, and a removed object guard), so the tests now pin the exception type and the message. Two older tests deliberately pinned "array → malformed" and were changed as the spec delta says. The 26b re-run went from 5 to 14 successful calls of 28, with 0 malformed (11 before). All M3 calls hit 503 or timeouts, so the M3 numbers say nothing about the LLM. Defaults unchanged (PR #106).
