---
when: Sun 03:04
who: Damian
---

## What was done with AI

A Claude Code session, started by the coordinating session, prepared the analytics hand-in demo end to end. It started a dedicated `iw-demo` stack from a detached `origin/main` worktree (one `docker compose up -d --build`, `.env` copied by a script that never prints values) and scanned the vetted sources. It looked for an M3 page above 0.4: the seeded Telegram channels are crypto-only and capped, so it found and tested a paid GPW-signals page against the S3.4 patterns before adding it through the API. It then warmed the LLM cache by re-announcing the demo documents and checked that a second pass makes no LLM request. It wrote `.docs/demo-analytics.md` from the stored findings.

## Outcome / lesson

M1 (0.94) and M2 (0.368) have Gemma verdicts in the cache, and the second pass made 0 Gemini requests. M3 (0.622) and the extra M1 stayed rules-only after 10 tries each: Gemini answered about one call in ten. Two lessons for warming a hosted model through a breaker. First, space the tries past the breaker's cooldown, because back-to-back documents only ever get the one trial call. Second, quote `*` in `redis-cli XADD` inside `sh -c`, because the shell globbed it and the first round re-announced nothing. Near-dup turned out not to need embeddings (MinHash), but there was no real repost to show. After the coordinator pointed at the shared demo flow (PR #118), the script was rewritten as a per-step mapping onto that flow, with the remaining sources scanned to match it. That surfaced three places where the flow's predictions no longer hold on `main`: the slider numbers, which finding drops at M2 0.40, and the `down -v` step, which would wipe the warmed cache.
