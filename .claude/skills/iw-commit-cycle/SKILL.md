---
name: iw-commit-cycle
description: Use while running /openspec-apply-change, each time a task group is done and about to be committed, and before any follow-up fix commit on an open PR. Adds the test-first proof, the commit rules and the review step around OpenSpec's apply; does not replace /openspec-apply-change. Skip the review for docs-only commits.
---

# iw-commit-cycle

Runs inside `/openspec-apply-change`. OpenSpec picks the tasks and ticks them; this skill defines what "done and committed" means. Per **task group** (the tasks that make one coherent commit):

1. **Test first.** The group's first task is a failing test. Name the production change that would turn it red, run it, and confirm it fails for the intended reason (not an import error). Parsers and fixtures: saved real responses under `tests/fixtures/`, never live network in unit tests. (`ecc:tdd-guide` may be used if installed; it is not required.)
2. **Implement** the minimum, run the test green, then the module's full suite, lint and type check. Keep the command and result; a run before the last edit does not count.
3. **Validate**: `openspec validate <slug> --strict`, and `node .claude/skills/iw-docs-update/scripts/docs-check.mjs` if you touched docs or added a service directory.
4. **Stage, then commit, as two separate tool calls** (`git add <paths>`, then `git commit`). The `git-guard` hook reads the staged diff when the command starts, so a chained `git add ... && git commit` is denied. Conventional Commit, terse subject, no `Co-Authored-By`. If the hook denies a commit, fix the cause; don't reach for an escape flag, and if one is genuinely needed ask the human and report its use in the PR body.
5. **Review** once per task group, and before every push, whichever comes first (not after every single commit). Dispatch the `iw-reviewer` agent (in `.claude/agents/`; `/code-review` is the fallback) with: the worktree path, the pinned range `BASE=$(git merge-base HEAD origin/main)` to the HEAD sha, the change name, and `focus: security` for contract, credential, proxy, outbound-request or LLM-prompt changes. It reads and reports; it does not edit.
6. **Verify every finding** against the code before acting. Fix real ones in follow-up commits (never amend a pushed commit); reject false ones with a one-line evidence note. After 3 rounds on one group, stop and ask the human.
7. **Triage out-of-scope findings** and the reviewer's "declined to judge" list into the change's `follow-ups.md` (create it if absent), one row each with one disposition: `fix-here`, `new-item` (GitHub issue), `wont-fix` (reason) or `docs`.

Each review is a fresh agent; nothing is carried across sessions.
