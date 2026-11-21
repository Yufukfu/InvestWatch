---
name: iw-ai-log
description: Use at each integration milestone, after a PR merges, and whenever an agent or rule misled you. Appends one dated entry to doc/ai-log.md, the evidence for the "AI-assisted process" jury criterion. Not a place for secrets or raw transcripts.
---

# iw-ai-log

`doc/ai-workflow.md` explains the process; `doc/ai-log.md` is the append-only evidence. Add an entry (newest at the bottom) with:

```markdown
## 2026-11-21 14:30 · <module> · <change-name or milestone>
- **Task:** one line.
- **Prompt that worked / failed:** a short, redacted excerpt and why.
- **What the agent got wrong:** and how review or a test caught it (or "nothing").
- **Human decision:** what the human overrode or approved.
- **Evidence:** PR number, commit sha, test command.
```

Rules: UTC or local time stated once in the file header, never edit old entries, no tokens/keys/proxy credentials/personal data, one entry per merged PR or milestone (not per commit). If an agent, skill or hook gave wrong guidance, say which one so we can fix it in `.claude/`.
