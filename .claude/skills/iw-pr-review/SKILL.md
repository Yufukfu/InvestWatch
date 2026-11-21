---
name: iw-pr-review
description: Use once, before opening a PR from a finished OpenSpec change, as the final whole-branch gate. Verifies the branch against its spec, runs the dependency and secret checks the jury scores, and prepares the PR body. Never pushes or opens the PR itself.
---

# iw-pr-review

Per-commit review already ran (`iw-commit-cycle`). This is the last pass over the whole branch.

1. **Pin the range**: `BASE=$(git merge-base HEAD origin/main)..HEAD`.
2. **Deterministic first, all green**:
   - the module's tests, lint and type check, run after the last code edit;
   - `openspec validate --all --strict`;
   - `node --test ".claude/hooks/*.test.js"` if hooks changed;
   - dependency scan for the touched module: `pip-audit` (Python) or `npm audit` (Node);
   - `git grep -nE "console\.log|print\(" -- <module>` has no debug leftovers, and no `.env` or key material is tracked;
   - `docker compose up` still starts the stack when a service or its Dockerfile changed (merge rule in `doc/plan-integracji.md` §7).
3. **One whole-branch review** with `ecc:code-reviewer` (or `/code-review`) on the pinned range, plus `ecc:security-reviewer` when the diff touches proxies, credentials, outbound requests built from stored URLs, or LLM prompts built from scraped text. Scale effort to blast radius: contract or cross-module change gets both, a parser tweak gets one.
4. **Verify every finding** against the code (see `.claude/CODE_REVIEW.md`); fix the real ones.
5. **Follow-ups**: every row in `follow-ups.md` has a disposition. Every behaviour change a teammate would notice (new field, changed default, removed state) is one line in the PR body.
6. **Hand the draft PR body to the human** (one sentence of why, the change name, the test command and result). The human gives the go-ahead to push and open the PR. After merge: `/openspec-archive-change`, update `doc/STATUS.md`, then `iw-ai-log`.

Optional, high-risk diffs only (contract changes, anything handling credentials): a second reviewer from a different model family (see `.claude/CODE_REVIEW.md`).
