---
when: Sun ~02:00
who: Damian
---

## What was done with AI

A Claude Code side session proposed and applied `analytics-embeddings` (stage 3: embeddings, topic gate, near-dup) under the coordinator session: OpenSpec plan trimmed by Damian, then 9 task groups test-first with a scripted mutation check per group (all mutants caught after fixes) and a fresh `iw-reviewer`-style subagent per group. Synced by rebase onto the moving `analytics-llm-p0` branch until the first push.

## Outcome / lesson

Branch `analytics/analytics-embeddings`, issue #65 for infra. Reviews caught real bugs the tests had missed: untyped `OverflowError`/`RecursionError` and lone surrogates in the client, a non-UTF-8 cache value raising, a spam flood making near-dup O(N) per copy, alert claims burned by a failed publish, and compose passing `EMBED_MODEL=""`. A coordinator question exposed that datasketch loads scipy (about 115 MB), so the MinHash is our own numpy code pinned to datasketch's legacy scheme by a golden vector. Testing the wiring showed the dictionary gate dropping real M3 advisory offers with no market word; advisory cues were added. Lesson: a pure-function test of a filter is not enough, so compare the pipeline's findings with and without it.
