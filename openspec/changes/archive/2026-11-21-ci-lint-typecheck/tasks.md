# Tasks

## 1. Workflow

- [x] 1.1 Add `npm run lint --if-present` and `npm run typecheck --if-present` to the Node loop in `.github/workflows/ci.yml`; validate the YAML parses and run the same commands in `web/`.
- [x] 1.2 Mutation check: introduce a lint error in a scratch copy of `web/`, run the loop's command chain, and confirm it exits non-zero. Record `mutations: N tried, N caught`. A `console.log` added to a scratch copy of `web/` made the chain exit 1. mutations: 1 tried, 1 caught. The CI run itself is not verified until the workflow runs on GitHub.

## 2. Closing

- [x] 2.1 `iw-docs-update`: `.docs/ai-workflow.md` row, `docs-check` clean.
- [x] 2.2 `iw-pr-review`: no reviewer agent run (two-command workflow change); the PR is reviewed by B and hen68.

## Workflow follow-up

- Archive last; separate PR from #12 if #12 is already merged, else on the same branch.
