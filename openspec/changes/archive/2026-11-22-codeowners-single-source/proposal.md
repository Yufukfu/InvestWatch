# Proposal

## Why

PR #48 added `.github/CODEOWNERS`, and the `iw-watch` runner reads it to route reviews and defect reports. The same mapping is still restated in about 25 live files: the root `CLAUDE.md` and `README.md` tables, `.docs/STATUS.md`, the status file titles, every service `CLAUDE.md` and `README.md`, `.docs/integration-plan.md`, `.docs/analytics-plan.md`, `openspec/config.yaml`, `.claude/SDLC.md`, `.claude/rules/web-dashboard.md`, the module `compose.yaml` headers and one spec purpose. They already disagree. `CODEOWNERS` leaves `infra/` shared on purpose (its test pins that), while `CLAUDE.md`, `README.md`, `infra/CLAUDE.md`, `infra/README.md` and `.docs/STATUS.md` say Kacper owns it. `CODEOWNERS` also points back at a copy: its header says "the split in .docs/STATUS.md".

## What Changes

- `.github/CODEOWNERS` becomes the only file that maps paths to people. The module lines stay as merged (`scraper/` `@hen68`, `web/` `@kacpermalczyk`, `analytics/`, `api/`, `contracts/` `@Yufukfu`). Shared areas (`infra/`, root files, `.docs/`, `.claude/`, `openspec/`, `.github/`) stay with no owner, so GitHub requests no extra reviews. Its header now says it is the source of truth instead of pointing at `.docs/STATUS.md`.
- **Process change.** `infra/` is shared, and a new top-level directory needs the whole team's OK instead of Kacper's alone.
- Ownership statements are removed from every live doc and replaced with a link to `.github/CODEOWNERS`. ADRs, the AI log and archived changes are history and stay as written. The per-person ADR number ranges stay as well: they prevent number collisions and say nothing about ownership.
- `docs-check` gains two rules:
  - Every existing service directory has a `/<dir>/` line in `CODEOWNERS` with at least one `@handle`.
  - Live docs (plus `openspec/config.yaml` and the `compose.yaml` files) contain no per-person ownership statement: `owner <Name>`, `owned by <Name>`, `<Name>'s module`, `<dir> (<Name>)` or an `Owner` table column.
- ADR 0211 records the decision. It partly supersedes ADR 0202 (the consequence that Kacper owns the layout) and ADR 0205 (status domains mapped to people).

## Capabilities

### New Capabilities

None. This is repository process and tooling, not system behaviour, so `skip_specs: true` is set (precedent: `ci-lint-typecheck`).

### Modified Capabilities

None. The `web-foundation` purpose line loses its owner name, which changes no requirement.

## Impact

- Shared change (process, `.github/`, `.claude/`, `.docs/`), proposed by Kacper.
- No contract, REST route, event or `iw-watch` behaviour changes. `CODEOWNERS` keeps the same rules, so review routing is unchanged.
- Out of scope: changing who owns a module, adding owners for the shared areas, required code-owner review (a branch-protection setting), editing ADRs or AI log rows.
