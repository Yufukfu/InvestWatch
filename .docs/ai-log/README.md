# AI log

One file per entry: what we did with an AI assistant and what we learned. This is the evidence for the "standardized software development process with AI assistants" criterion. The process itself is described in [`../ai-workflow.md`](../ai-workflow.md). Why it is one file per entry: [ADR 0212](../decisions/0212-ai-log-one-file-per-entry.md).

- **Add an entry:** `node .claude/skills/iw-ai-log/scripts/ai-log.mjs new <adam|kacper|damian> <change-name>`, then fill in both sections. The rules are in the `iw-ai-log` skill.
- **Read it as one table:** `node .claude/skills/iw-ai-log/scripts/ai-log.mjs render`
- **Validate:** `node .claude/skills/iw-ai-log/scripts/ai-log.mjs check` (runs in CI)

File names sort in time order: `YYYY-MM-DDTHHMM-<who>-<slug>.md`, in local time to match the `when:` values. For entries moved from the old table that only had "pm" or "morning", the time in the file name is approximate; `when:` keeps the original text.
