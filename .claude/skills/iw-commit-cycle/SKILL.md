---
name: iw-commit-cycle
description: Use for every commit while implementing an OpenSpec change, and before any follow-up fix commit on an open PR. Defines the per-commit loop of tdd-guide then code-reviewer on a pinned range; skip only for docs-only commits.
---

# iw-commit-cycle

Per commit, in this order:

1. **Failing test first** (`ecc:tdd-guide`). Name the production change that would turn the test red. Run it and confirm it fails for the intended reason (not an import error). Fixtures and parsers: use saved real responses under `tests/fixtures/`, never live network in unit tests.
2. **Implement** the minimum, run the test green, then the module's full suite plus lint and type check. Keep the command and result; a run before the last edit does not count.
3. **Tick the task** in `openspec/changes/<slug>/tasks.md`, run `openspec validate <slug> --strict`, and `node .claude/skills/iw-docs-update/scripts/docs-check.mjs` when you touched docs or added a service directory.
4. **Commit** (Conventional Commit, terse subject, no body unless essential, no `Co-Authored-By`). The `git-guard` hook blocks `.env`, `console.log` and service code with no active change.
5. **Review the commit** with `ecc:code-reviewer`. Pin the range: `BASE=$(git merge-base HEAD origin/main)`, the HEAD sha and the worktree path. Ask for plan compliance against the change's `proposal.md` and `specs/`: missing, extra, misunderstood. The reviewer reads and reports; it does not edit, commit or spawn agents. Anything it can't confirm from the diff goes in a "can't verify" list; anything it set aside as out of scope goes in a "declined to judge" list.
6. **Verify every finding** against the code before acting. Fix the real ones in follow-up commits (never amend a pushed commit); reject false ones with a one-line evidence note. After 3 rounds on one commit, stop and ask the human.
7. **Triage out-of-scope findings** into the change's `follow-ups.md` (create it if absent) as a table row with exactly one disposition: `fix-here`, `new-item` (GitHub issue), `wont-fix` (reason) or `docs`.

Review session note: the reviewer is a fresh agent per commit. It is not carried across sessions.
