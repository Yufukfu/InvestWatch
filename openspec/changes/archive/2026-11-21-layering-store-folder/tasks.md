# Tasks

## 1. Store folder pattern

- [x] 1.1 Write a failing case in `web/src/layering.test.ts`: a component importing `../../../store/index` is rejected.
- [x] 1.2 Add `**/store/**` to `web/.oxlintrc.json`; verify tests, lint, typecheck.
- [x] 1.3 Mutation check: drop `**/store/**`; record `mutations: N tried, N caught` on this line. mutations: 1 tried, 1 caught.

## 2. Closing

- [x] 2.1 `iw-docs-update`: list the uncovered cases in `.claude/rules/web-dashboard.md`, AI log row, `docs-check` clean.
- [x] 2.2 `iw-pr-review`: small docs and one-pattern change, reviewed with the PR range. No reviewer agent run: one pattern plus docs, covered by the PR #12 review that approved it.

## Workflow follow-up

- Archive last, push, fix the PR body test count.
