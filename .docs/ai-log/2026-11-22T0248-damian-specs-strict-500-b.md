---
when: Sun 03:00
who: Damian
---

## What was done with AI

After #106 and #109 merged, `npx @fission-ai/openspec@2.1.1 validate --all --strict` on `main` was 30/32 again: one requirement in `llm-analysis` and one in `mock-api` were over 500 characters before their first scenario. The analytics coordinating Claude Code session moved the extra sentences verbatim into AND lines of the existing scenarios, with no behaviour change.

## Outcome / lesson

Strict validation is back to 32/32. The same over-limit problem has slipped into `main` three times, because the merged PRs were validated with an unpinned local `openspec` 1.2.0, which has no 500-character check. Validate only with the pinned `npx @fission-ai/openspec@2.1.1`.
