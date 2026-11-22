---
name: iw-ai-log
description: Use as part of closing an OpenSpec change (same PR, before archiving), at each integration milestone, and whenever an agent or rule misled you. Adds one entry file to .docs/ai-log/, the team's evidence for the "AI-assisted process" jury criterion. Not a place for secrets or raw transcripts.
---

# iw-ai-log

The AI log is one file per entry in `.docs/ai-log/` ([ADR 0212](../../../.docs/decisions/0212-ai-log-one-file-per-entry.md)). Parallel PRs add different files, so they never conflict. Never add a row to a table in `.docs/ai-workflow.md`.

1. Create the entry. `who` is the person you work for, and the slug is usually the OpenSpec change name:
   ```sh
   node .claude/skills/iw-ai-log/scripts/ai-log.mjs new kacper trend-chart-review-fixes
   ```
   This prints the path, for example `.docs/ai-log/YYYY-MM-DDTHHMM-kacper-trend-chart-review-fixes.md`. Pass a third argument to set `when:` (for example `"Sun ~10:00"`); otherwise it is the current day and time.
2. Replace both `TODO`s:
   - `## What was done with AI`: the task and the prompt approach that worked or failed (short, redacted).
   - `## Outcome / lesson`: the PR number or commit, what the agent got wrong and how review or a test caught it, and what the human decided.
3. `node .claude/skills/iw-ai-log/scripts/ai-log.mjs check` must pass (CI runs it too).

Rules:
- Never edit another PR's entry; correct your own in your own PR.
- The entry goes in the same PR as the work. One entry per change or milestone, not per commit.
- No tokens, keys, proxy credentials or personal data.
- If an agent, skill or hook gave wrong guidance, name it so we fix it in `.claude/`.
- If the process itself changed, also update the matching section of `.docs/ai-workflow.md` in a small separate edit.
- An older branch that still adds a row to the old table: take `main`'s `.docs/ai-workflow.md` and move the row into an entry with `new`.

To read the whole log as one table: `node .claude/skills/iw-ai-log/scripts/ai-log.mjs render`.
