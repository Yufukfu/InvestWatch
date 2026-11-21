---
name: iw-pr-review
description: Use as the review task near the end of an OpenSpec change (generated into tasks.md), once all implementation tasks are done and before archiving. Runs the deterministic checks and one whole-branch review, then drafts the PR body. The "ready" criteria live in .claude/CODE_REVIEW.md. Never pushes or opens the PR.
---

# iw-pr-review

Task-group reviews already ran (`iw-commit-cycle`). This is the last pass over the whole branch. Criteria: `.claude/CODE_REVIEW.md`; this skill holds the commands.

1. **Pin the range**: `BASE=$(git merge-base HEAD origin/main)`, `HEAD` sha, worktree path.
2. **Deterministic checks, all green, run after the last code edit:**
   - the module's tests, lint and type check;
   - every task group has its `mutations: N tried, N caught` line (`iw-commit-cycle` step 3); a group with surviving mutants or no line is not done;
   - `openspec validate --all --strict`;
   - `node .claude/skills/iw-docs-update/scripts/docs-check.mjs`, and `iw-docs-update` has been applied;
   - `node .claude/skills/iw-pr-review/scripts/test-diff-check.mjs --base origin/main` (use the PR's base branch): flags a deleted test file, added skip/xfail/only markers or fewer assertions than at the merge-base. A flag is a question, not a verdict: explain it in the PR body or fix it;
   - `node --test ".claude/hooks/*.test.js" ".claude/skills/iw-docs-update/scripts/*.test.mjs" ".claude/skills/iw-pr-review/scripts/*.test.mjs"` if hooks or the scripts changed;
   - dependency scan of the touched module: `pip-audit` (Python) or `npm audit` (Node), plus Gitleaks on the staged or branch changes (`.docs/supply-chain.md` §4); OSV-Scanner only through CI or on a machine with enough memory (§2), never a full-repo run on a developer laptop; the results go in the PR body's "Security scans" section, not in `.docs/security-audit.md`;
   - no debug leftovers: `git grep -nE "console\.log" -- '*.js' '*.jsx' '*.ts' '*.tsx' ':!*.test.*'` and, for Python, `git grep -nE "^\s*print\(" -- '*.py' ':!*test*'` (Python uses the logger; this one is checked by review, not by the hook); no `.env` or key material tracked;
   - `docker compose up` still starts the stack, **once `docker-compose.yml` exists** and a service or Dockerfile changed (merge rule, `.docs/integration-plan.md` §7).
3. **One whole-branch review**, only after step 2 is green: dispatch `iw-reviewer` on the pinned range (`/code-review` is the fallback) with `already-reported:` (the group reviews' findings and their dispositions) and `security: yes` for contracts, credentials, proxies, outbound requests from stored URLs or LLM prompts built from scraped text. One call covers both; never run a separate normal and security pass. Its job here is what group reviews cannot see: cross-group interactions and spec SHALLs left unimplemented.
4. **Verify every finding** against the code and fix the real ones (rules in `.claude/CODE_REVIEW.md`). Re-review only the fix commits, and only if a fix changed logic.
5. **Follow-ups and PR body**: every row in `follow-ups.md` has a disposition; the reviewer's "could not check" items go in the PR body. Draft the PR body: one sentence of why, the change name, the test command and result, a "Security scans" section (commands, versions, result, any residual risk), and one line for every behaviour change a teammate would notice and for any `IW_*` escape that was used.
6. **Hand back to the apply flow.** Closing continues with `/openspec-archive-change` as the last commit (see the config guidance), then, once the criteria in `.claude/CODE_REVIEW.md` hold, push the branch and open the PR with the drafted body (never `main`, never `--force`). Stop there: the human approves and merges.

Optional, high-risk diffs only (contract changes, anything handling credentials): a second reviewer from a different model family, see `.claude/CODE_REVIEW.md`.
