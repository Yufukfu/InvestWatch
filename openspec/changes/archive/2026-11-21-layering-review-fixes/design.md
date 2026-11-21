# Design

## Context

Findings in the PR #12 review; each was reproduced by the reviewer with the installed oxlint or a scratch mutation.

## Decisions

- **Real-component lint test over a CI workflow edit.** The test runs `oxlint -c web/.oxlintrc.json src/features/*/components` from `web/` and asserts exit 0. It keeps the change inside `web/` (CI already runs `npm test`). Adding `npm run lint` and `typecheck` to `ci.yml` is still worth doing; it is a one-line follow-up for whoever owns the workflow.
- **Relative `data` patterns at any depth** (`../**/data`, `../**/data/**`), replacing the depth-specific ones. Trade-off accepted: any relative import through a folder named `data` is treated as the data layer, so a future `shared/data` folder needs another name. The lint message says so.
- **`**/*Page` and `**/*Page.*`** for pages; package groups `name` and `name/**`, and `paths` entries removed in favour of one `patterns` group per package.
- **`model.ts` with types only** for health and summary: ADR 0204 says flat DTOs get no mapper; a shared prop type needs a home that both the hook and the component can import without the data layer depending on components. No mapper is added.
- **`HealthBadge`** renders `LABEL[state] ?? state`, the pre-refactor behaviour for an out-of-contract status.
- **Polling** is asserted by mocking the generated hook in its own test file and checking `pollingInterval: 30000`; the parameter is removed.

## Risks

- Broader `data` pattern can reject a harmless folder named `data`; documented above.
