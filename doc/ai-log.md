# AI work log

Append-only evidence for `ai-workflow.md`. Times are local (Europe/Warsaw). Format and rules: `.claude/skills/iw-ai-log/SKILL.md`.

## 2026-11-21 · A · SDLC setup (chore/sdlc-claude-setup)
- **Task:** design the AI-assisted SDLC (OpenSpec, skills, hooks, CI) by adapting the Neopadel pilot.
- **Prompt that worked:** pointing the agent at the existing neopadel `SDLC.md`/`CODE_REVIEW.md` and asking for a keep/leave table before any file was written.
- **What the agent got wrong:** the first hook draft would have blocked committing `scraper/CLAUDE.md` (markdown counted as service code); noticed while checking which files this PR would commit, fixed, and pinned with a regression test.
- **Human decision:** all-in-one PR; per-commit review stays a per-session practice for now; TLS-impersonating clients are the default fetch layer.
- **Evidence:** `node --test ".claude/hooks/*.test.js"`.
