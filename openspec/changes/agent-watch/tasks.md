# Tasks

Layout: `.claude/skills/iw-watch/` with `SKILL.md`, `scripts/watch.mjs`, `scripts/lib/*.mjs` and `scripts/*.test.mjs` (run with `node --test`). Fixtures are saved real `gh` JSON under `scripts/fixtures/`, never live network in unit tests.

## 1. CODEOWNERS and owner resolution

- [ ] 1.1 Write the failing test `codeowners.test.mjs`: last match wins, directory and glob patterns, no match, missing file, unknown syntax fails closed; run it and confirm it fails because the module does not exist
- [ ] 1.2 Add `.github/CODEOWNERS` (`scraper/` hen68, `web/` and `infra/` kacpermalczyk, `analytics/` `api/` `contracts/` Yufukfu) and `lib/codeowners.mjs`; verify the test passes and `node -e` resolves `infra/compose.yaml` to `kacpermalczyk`
- [ ] 1.3 Mutation check for this group: last-match order, directory prefix boundary (`web/` vs `web-old/`), fail-closed branch. Write the result on this line: `mutations: _ tried, _ caught`

## 2. State, lock and round count

- [ ] 2.1 Write the failing tests `state.test.mjs`: atomic write, corrupt file moved aside and reported, `ack` semantics, lock acquired and released, stale lock (older than 30 minutes) replaced, second runner exits 0, round count is the larger of the `<!-- iw-watch -->` comments in a fixture and the sessions in the state
- [ ] 2.2 Implement `lib/state.mjs` and `lib/rounds.mjs`; verify the tests pass and a killed write leaves the previous file intact
- [ ] 2.3 Mutation check: temp-then-rename, stale threshold boundary, cap comparison `>=` vs `>`, the `max` of the two counts. `mutations: _ tried, _ caught`

## 3. Scan and ack without a model (`--mine`, `--review-requested`)

- [ ] 3.1 Write the failing tests `scan.test.mjs` on saved `gh` fixtures: new review, nothing new, closed PR dropped, review request, new head sha after my review, draft PR skipped, `gh` not authenticated and rate-limit errors exit non-zero with state unchanged
- [ ] 3.2 Implement `lib/gh.mjs` (argv only, no shell, JSON out), `lib/scan.mjs` and the `scan` and `ack` commands in `watch.mjs`; verify the tests pass and `node watch.mjs scan --mine --json` runs against this repository
- [ ] 3.3 Mutation check: `has this sha been reviewed`, draft filter, state-newer-than comparison. `mutations: _ tried, _ caught`

## 4. Headless run

- [ ] 4.1 Write the failing tests `run.test.mjs` and `prompt.test.mjs`: the prompt wraps third-party text in the data fence and never in argv, tells the agent to end bodies with the marker and to use no `IW_*` flag, branch names outside `[A-Za-z0-9._/-]` are refused, argv contains `--permission-mode dontAsk` and exactly the allow-list of the spec (push to `origin`, `gh pr create`, `gh pr comment`, `gh issue create`) with no `gh pr review|merge|ready`, `gh api`, network tool or `bypassPermissions`, `--dry-run` leaves the push and `gh` writes out of the allow-list and saves a draft, a stub `claude` whose push is denied leaves a draft and a `needs-human` notice
- [ ] 4.2 Verify the `claude -p` flags against `claude --help` on a machine that has the CLI (permission mode, allowed tools, output format, max turns), save the output as `scripts/fixtures/claude-help.txt`, and pin the flag names in a test
- [ ] 4.3 Implement `lib/prompt.mjs`, `lib/worktree.mjs`, `lib/session.mjs`, `lib/notify.mjs` and the `run` command (round cap check, worktree removed unless `needs-human`, `draft-ready` and `needs-human` notices); verify the tests pass and a `--dry-run` against a fixture PR writes a draft and posts nothing
- [ ] 4.4 Mutation check: allow-list contents, `dontAsk` flag, fence wrapper, marker instruction, cap check, no-shell notify spawn, the dry-run switch. `mutations: _ tried, _ caught`

## 5. Domain overlay and owner-routed issues

- [ ] 5.1 Write the failing tests `domain.test.mjs`: `--author`, `--domain scraper`, `--domain mine`, unknown directory exits non-zero before fetching, CODEOWNERS read from the default branch even when a PR edits it, the owner-routed issue prompt names the owner and the path and the duplicate rule
- [ ] 5.2 Implement the filters in `lib/scan.mjs` and the issue branch in `lib/prompt.mjs`; verify the tests pass
- [ ] 5.3 Mutation check: the path-prefix match, `mine` expansion, default-branch read, the duplicate rule in the prompt. `mutations: _ tried, _ caught`

## 6. Skill, schedule example and CI

- [ ] 6.1 Write `SKILL.md` (when to use it, session flow with `/loop 2m /iw-watch --mine`, how to handle each item kind, what never to do, how to read a draft) and a `schedule/` example for launchd and cron; verify with `node .claude/skills/iw-docs-update/scripts/docs-check.mjs` and by following the file once on this repository
- [ ] 6.2 Add `.claude/skills/iw-watch/scripts/*.test.mjs` to the node test step in `.github/workflows/ci.yml`; verify `node --test ".claude/skills/iw-watch/scripts/*.test.mjs"` is green
- [ ] 6.3 Run the end-to-end check on a throwaway branch of this repository: open a PR, leave a review from a second account or fixture, confirm `scan` reports it, a headless run commits a fix, pushes the branch and comments with the marker, and that `gh pr review --approve` is denied in that session; record the PR URL in the PR body

## 7. Closing tasks

- [ ] 7.1 Apply the `iw-docs-update` skill: update `.claude/SDLC.md`, `.docs/ai-workflow.md` and `.docs/INDEX.md` (skill list, the scheduled-watcher flow), `.docs/status/dashboard.md`, add the `iw-ai-log` row, run `docs-check.mjs` clean. No ADR: the push and PR rule is ADR 0207, and the round-cap choice is in `design.md`
- [ ] 7.2 Run the `iw-pr-review` skill with `focus: security`, fix the real findings, and draft the PR body (it must say that the headless agent pushes and comments under ADR 0207); push and open the PR as ADR 0207 allows

## Workflow follow-up

- Run `/openspec-archive-change` as the last commit of the branch, after 7.2.
- The human approves and merges the PR.
