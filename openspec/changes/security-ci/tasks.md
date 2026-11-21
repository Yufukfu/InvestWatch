# Tasks

Owner Kacper. Nothing heavy runs on the laptop: OSV-Scanner and `pip-audit` are verified only in GitHub Actions. Locally the only runs are the Node pin test and one Gitleaks run (about 5 s) to check the allowlist. Mutation checks are small and targeted, not sweeps.

## 1. Pin test (~30 min)

- [x] 1.1 Failing test `.github/tests/workflow-pins.test.mjs` (node:test, no dependencies). It covers the pin-test scenarios: `uses:` by tag only fails, a `docker run` image without `@sha256:` fails, `pip install pip-audit` without `==` fails, and each failure names the line. A fully pinned sample passes. It also asserts that `.github/workflows/security.yml` exists and passes the same checks, so the test is red until group 2.
- [x] 1.2 Add `".github/tests/*.test.mjs"` to the test step of `ci.yml`'s `Specs and hooks` job (no other `ci.yml` change)
- [x] 1.3 Mutation check: remove each of the three rules in turn, plus the "names the line" check (once per rule); `mutations: 6 tried, 6 caught`

## 2. Security workflow and Gitleaks allowlist (~1 h)

- [x] 2.1 `.gitleaks.toml`: default rules plus one allowlist entry (description, path `contracts/mocks/generate_mocks.py`, `regexTarget = "line"`, regex for `key="m<digit>-…"`, `condition = "AND"`). Check it with one local Gitleaks run over `origin/main` (digest-pinned image, `--redact`, the worktree `.git` mount from the runbook): 0 findings and the commit count reported. Then a scratch copy of the mock file with a credential-shaped test value on a differently shaped line still fails. That copy is never committed.
  - Done: the entry sits on the `generic-api-key` rule (`[[rules.allowlists]]`), because a top-level `[[allowlists]]` with `paths` skipped the whole file in v8.28.0 whatever `condition` said, and the scratch line slipped through. Final config: `origin/main` (`c810a140`) 571 commits, 0 findings. Default rules only: 2 findings. Scratch copy with an added `upstream_api_key = "<random>"`: exactly that line is reported.
  - The runbook's worktree mount (`-v "$PWD:$PWD"`) shows an empty directory under Docker Desktop on this Mac, so Gitleaks scanned 0 commits. The local runs mounted the worktree and the common git dir at `/repo` and `/gitcommon` and set `GIT_DIR`, `GIT_COMMON_DIR` and `GIT_WORK_TREE`. The runbook is fixed in 4.1.
- [x] 2.2 `.github/workflows/security.yml` per design decisions 1-7:
  - triggers `pull_request` to `main` and `workflow_dispatch` with a boolean input `offline`
  - jobs `gitleaks` (`fetch-depth: 0`), `osv-scanner` (online), `pip-audit` (matrix as in `ci.yml`, `pip-audit==2.10.1`), `npm-audit` (`web/`, `--audit-level=high`) and `osv-scanner-offline` (only when `inputs.offline`)
  - `permissions: contents: read`, `concurrency`, timeouts
  - added: the Gitleaks step fails when its log has no `N commits scanned` with N > 0, because Gitleaks over an unreadable history exits 0 (checked locally: 0 commits, exit 0). `safe.directory` is passed by env for the root container.
- [x] 2.3 The pin test from group 1 is green against the real workflow. Run `node --test` for the hook, script and `.github/tests` suites. Result: 88 tests, 88 pass.
- [x] 2.4 Mutation check: tag one `uses:`, drop one image digest, unpin `pip-audit` (each must turn the pin test red); `mutations: 3 tried, 3 caught`

## 3. First runs in GitHub Actions (~30 min, after the push)

- [ ] 3.1 Push the branch and open the PR, which triggers the `pull_request` run. Every job must be green, or each red finding is fixed or documented as a residual risk in the PR body (ADR 0209 decision 2). Record each job's wall-clock time.
- [ ] 3.2 Start the workflow by hand on the branch with `offline: true`. Record whether the offline OSV-Scanner run finishes, its time and its result. This is the first verified OSV-Scanner run on this repository.

## 4. Closing

- [ ] 4.1 Apply `iw-docs-update`:
  - `.docs/supply-chain.md`: a CI section and an updated status table
  - ADR 0209 is not edited (accepted). The new facts go in the runbook and the status file.
  - `.docs/status/dashboard.md`
  - add the `iw-ai-log` row
- [ ] 4.2 Run `iw-pr-review` and fix real findings, with the reviewer told not to run Docker or scans locally
- [ ] 4.3 Put the "Security scans" section in the PR body with the Actions run links and times

## Workflow follow-up

- `/openspec-archive-change` as the last commit, then push. The human approves and merges.
- After the merge: start the workflow on `main` by hand and link that run in `.docs/security-audit.md` as the hand-in scan. That is a small docs PR, because nothing goes straight to `main`.
