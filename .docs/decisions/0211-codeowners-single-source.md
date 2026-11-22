# 0211. `.github/CODEOWNERS` is the only place that names owners

- Status: accepted
- Date: 2026-11-22
- Deciders: agent-written from Kacper's decision (change `codeowners-single-source`). It takes effect when the team approves and merges the PR. Partly supersedes [ADR 0202](0202-deployment-topology.md): its consequence that Kacper owns the root include list and `infra/`. Partly supersedes [ADR 0205](0205-status-per-domain.md): status domains mapped to people, and "edit only your own domain file".

## Context

PR #48 added `.github/CODEOWNERS`. GitHub requests the code owners' review from it, and the `iw-watch` runner reads it from the default branch to route reviews and defect issues (`.claude/skills/iw-watch/scripts/lib/codeowners.mjs`). On `main` after that merge, the same mapping was still written by hand in about 25 live files. Among them: the root `CLAUDE.md` and `README.md` tables, `.docs/STATUS.md`, every status file title, every service `CLAUDE.md` and `README.md`, `openspec/config.yaml`, `.claude/SDLC.md`, the module `compose*.yaml` headers and a spec purpose. The copies disagreed. `CODEOWNERS` leaves `infra/` without an owner on purpose (`codeowners.test.mjs`: "infra/ is shared: no owner"), but five docs said Kacper owns it. The `CODEOWNERS` header also pointed back at a copy ("the split in .docs/STATUS.md").

## Options considered

1. **Keep the prose and add `CODEOWNERS` beside it** (the state after PR #48). There are two sources. They already disagreed on `infra/`, and nothing checks them against each other.
2. **`CODEOWNERS` only, plus a `*` fallback that lists all three of us.** Every path gets an owner. But nearly every PR touches a shared file, because the root `CLAUDE.md` requires a status update in each PR. GitHub would then request the other two people on almost every PR, and every `iw-watch --review-requested` runner would start an agent review for each one. Kacper rejected this.
3. **`CODEOWNERS` only. Modules have owners, shared areas have none, and docs link to the file.** It has one source, routing stays the same as after PR #48, and `docs-check` keeps it that way.

## Decision

Option 3.

- `.github/CODEOWNERS` maps the modules to people: `scraper/`, `web/`, `analytics/`, `api/`, `contracts/`.
- Shared areas have no owner: `infra/`, `.docs/`, `.claude/`, `openspec/`, `.github/` and root files. Any teammate may change them. A new top-level directory needs the whole team's OK, no longer Kacper's alone.
- Other docs link to `CODEOWNERS` and never name an owner.
- Status files map to directories, and whoever changes a directory updates the file that covers it.
- `docs-check` enforces this. Every service directory needs a `/<dir>/` line with an `@handle`. A per-person ownership statement in a live doc fails the check (`owner <Name>`, `owned by <Name>`, `<Name>'s module`, `<dir> (<Name>)`, an `Owner` table column). ADRs, the AI log and OpenSpec changes are skipped because they are history or still in flight.
- The per-person ADR number ranges stay. They prevent number collisions and say nothing about ownership.

## Consequences

- Changing an owner is a one-line PR to `CODEOWNERS`, and GitHub and `iw-watch` follow it without doc edits.
- Nobody is asked automatically to review a change to a shared area. The author asks in the team chat when it matters.
- The ownership check is a pattern match. New wording (for example "Adam is responsible for `scraper/`") gets past it until a test and a pattern are added.
