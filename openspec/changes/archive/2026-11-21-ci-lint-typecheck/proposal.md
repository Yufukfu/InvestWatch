# Proposal

## Why

The CI `node` job runs `npm ci`, `npm audit` and `npm test` only. Lint and typecheck failures (for example `no-console`, `react/no-danger`, type errors) never fail CI; the layering guard is covered only because a test lints the components. Raised in the PR #12 review, approved by B (module owner).

## What Changes

- In `.github/workflows/ci.yml`, the Node loop also runs `npm run lint --if-present` and `npm run typecheck --if-present` before the tests.

**Out of scope:** other CI jobs, making CI a required check (SDLC stage 8 stays advisory), any `web/` code.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
<!-- none -->

## Impact

- `.github/workflows/ci.yml`; `.claude/SDLC.md` stage 8 wording unchanged. AI log row.
