# 0205. Status split per domain

- Status: accepted
- Date: 2026-11-21
- Deciders: agent-written; accepted by the team (decision taken in the team chat), effective when the human merges the PR

## Context

`.docs/STATUS.md` held the milestones, one table row per module and a blocker list. Three people edit it in every PR (the root `CLAUDE.md` requires a status update before any PR). The module rows are single table lines of 168, 800 and 1076 characters on `origin/main`, and the file changed in 35 commits. Git merges by line, so two edits to the same row conflict even when they touch different sentences. The existing rule "edit only your own module's row" limits this but does not remove it: a row is still one line, and the shared blocker list is edited by everyone.

The rule is stated in the root [`CLAUDE.md`](../../CLAUDE.md), [`.claude/SDLC.md`](../../.claude/SDLC.md), `iw-docs-update` and `iw-implement`, so changing it is a process change.

## Options considered

1. **Keep one file, split rows into bullets.** Fewer conflicts inside a row, but all three owners still edit one file and the shared blocker list.
2. **One file per domain, `.docs/STATUS.md` keeps a one-sentence summary per domain.** No shared lines for module state, but the summaries must still be edited by hand in `.docs/STATUS.md`, so the conflict moves there.
3. **One file per domain, `.docs/STATUS.md` keeps only team-wide information and links.** Module state and module blockers are edited in exactly one owner's file; `.docs/STATUS.md` changes only when a milestone moves or a team-wide decision opens.

## Decision

Option 3. `.docs/status/scraper.md` (Adam), `.docs/status/dashboard.md` (Kacper) and `.docs/status/platform.md` (Damian: analytics, api, contracts) hold state, active OpenSpec changes and the blockers of that domain, written as bullets. `.docs/STATUS.md` holds milestones, the links, and blockers that need the whole team. Rule: edit only your own domain file; changing another owner's file needs their OK. A blocker goes in the file of the domain it blocks.

Rationale: options 1 and 2 leave a line that several people edit; only option 3 removes every shared line for routine updates (evidence above: 35 commits to one file, rows up to 1076 characters). The team accepted it.

## Consequences

- Routine PRs touch only their owner's file, so status no longer causes merge conflicts.
- An agent reads `.docs/STATUS.md`, then the file of its domain; there is no single page with the whole picture, only links.
- Domains map to people, not directories. If ownership changes, the file is renamed in a docs-only PR.
- The change touches no code and no contract.
