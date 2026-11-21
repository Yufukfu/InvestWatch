---
name: iw-ai-log
description: Use at each integration milestone, after a PR merges, and whenever an agent or rule misled you. Appends one row to the Log table in doc/ai-workflow.md, the team's evidence for the "AI-assisted process" jury criterion. Not a place for secrets or raw transcripts.
---

# iw-ai-log

`doc/ai-workflow.md` holds the process description and, at the bottom, the Log table. Append one row at the end of the table, same columns as the existing rows:

| When | Who | What was done with AI | Outcome / lesson |
|---|---|---|---|
| Sat 14:30 | A | the task and the prompt approach that worked or failed (short, redacted) | PR number or commit, what the agent got wrong and how review or a test caught it, what the human decided |

Rules: never edit old rows; one row per merged PR or milestone, not per commit; no tokens, keys, proxy credentials or personal data; if an agent, skill or hook gave wrong guidance, name it so we fix it in `.claude/`. If the process itself changed, also update the matching section above the table.
