---
name: iw-pr-review
description: Use as the review task near the end of an OpenSpec change (generated into tasks.md), once all implementation tasks are done and before archiving. Runs the deterministic checks and one whole-branch review, then drafts the PR body. The "ready" criteria live in .claude/CODE_REVIEW.md. Never pushes or opens the PR.
---

# iw-pr-review

Task-group reviews already ran (`iw-commit-cycle`). This is the last pass over the whole branch. Criteria: `.claude/CODE_REVIEW.md`; this skill holds the commands.

1. **Pin the range**: `BASE=$(git merge-base HEAD origin/main)`, `HEAD` sha, worktree path.
2. **Deterministic checks, all green, run after the last code edit:**
   - the module's tests, lint and type check;
   - `openspec validate --all --strict`;
   - `node .claude/skills/iw-docs-update/scripts/docs-check.mjs`, and `iw-docs-update` has been applied;
   - `node --test ".claude/hooks/*.test.js" ".claude/skills/iw-docs-update/scripts/*.test.mjs"` if hooks or the checker changed;
   - dependency scan of the touched module: `pip-audit` (Python) or `npm audit` (Node);
   - no debug leftovers: `git grep -nE "console\.log" -- '*.js' '*.jsx' '*.ts' '*.tsx' ':!*.test.*'` and, for Python, `git grep -nE "^\s*print\(" -- '*.py' ':!*test*'` (Python uses the logger; this one is checked by review, not by the hook); no `.env` or key material tracked;
   - `docker compose up` still starts the stack, **once `docker-compose.yml` exists** and a service or Dockerfile changed (merge rule, `.docs/integration-plan.md` §7).
3. **One whole-branch review**: dispatch `iw-reviewer` on the pinned range (`/code-review` is the fallback), with `focus: security` for contracts, credentials, proxies, outbound requests from stored URLs or LLM prompts built from scraped text. A contract or cross-module change gets both a normal and a security pass; a parser tweak gets one.
4. **Verify every finding** against the code and fix the real ones (rules in `.claude/CODE_REVIEW.md`).
5. **Follow-ups and PR body**: every row in `follow-ups.md` has a disposition. Draft the PR body: one sentence of why, the change name, the test command and result, and one line for every behaviour change a teammate would notice and for any `IW_*` escape that was used.
6. **Hand back to the apply flow.** Closing continues with `/openspec-archive-change` as the last commit (see the config guidance), then the human decides on the push and the PR.

Optional, high-risk diffs only (contract changes, anything handling credentials): a second reviewer from a different model family, see `.claude/CODE_REVIEW.md`.
