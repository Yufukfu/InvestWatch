# Proposal

## Why

hen68's approving review of PR #12 found that `../../../store/index` is not blocked (only `**/store` and `**/store.*`), and asked that the cases the guard does not cover are written down.

## What Changes

- Add `**/store/**` to the restricted patterns, with a layering test case.
- State in `.claude/rules/web-dashboard.md` what the guard does not catch (alias or absolute paths, a sibling `./data` folder, a `model.ts` that re-exports from `data/`, dynamic `import()`).

**Out of scope:** CI lint/typecheck steps (workflow, owner Kacper), fake-timer polling test. No spec change: the requirement already says "the store".

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
<!-- none -->

## Impact

- `web/.oxlintrc.json`, `web/src/layering.test.ts`, `.claude/rules/web-dashboard.md`, AI log row.
