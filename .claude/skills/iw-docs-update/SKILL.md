---
name: iw-docs-update
description: Use as the closing task of every OpenSpec change (generated into tasks.md), and before any commit that changes behaviour, a contract, a service's config or run steps, or a decision. Says which doc to update for which change, how ADRs are drafted, and runs the deterministic docs-check. Not for editing openspec/specs by hand (archive does that).
---

# iw-docs-update

Docs hold the logic; `CLAUDE.md` files stay short and point at them. Update docs in the same PR as the code, then run the check.

## If you changed X, update Y

| Change | Update |
|---|---|
| A contract (`ScrapedDocument`, `Finding`, a REST route, an event) | `contracts/` schema and mocks, `.docs/integration-plan.md` (§3-§6), the OpenSpec change's spec delta, consumers' tests. Needs the whole team and a version bump. |
| A service's run steps, env vars or definition of done | that service's `README.md` (people and jury: purpose, how to run, config) and `CLAUDE.md` (agents: rules and pointers; no duplication of the README), `.env.example`, and the root README Quick Start once it exists |
| A new service directory | its own `CLAUDE.md`, a line in `.github/CODEOWNERS`, a row in the root `CLAUDE.md` services table, a row in `.docs/INDEX.md` |
| System behaviour | the OpenSpec change (`/openspec-archive-change` merges it into `openspec/specs/`). Never hand-edit `openspec/specs/`. |
| Module state, active changes, a module blocker appeared or cleared | the file in `.docs/status/` that covers the directories you changed (`.docs/status/scraper.md`, `.docs/status/dashboard.md` or `.docs/status/platform.md`; the map is in `.docs/STATUS.md`), never one for directories you didn't touch (limits merge conflicts) |
| Who owns which path | `.github/CODEOWNERS` only; other docs link to it and never name an owner (docs-check fails on one) |
| A milestone moved, or a team-wide decision opened or closed | `.docs/STATUS.md` (the owner of the milestone edits its row) |
| The process, a skill or a hook | `.claude/SDLC.md` or `.claude/CODE_REVIEW.md`, and `.docs/ai-workflow.md` |
| A hard-to-reverse choice | an ADR (below) |
| A change closing, or a milestone | one row in the Log table of `.docs/ai-workflow.md` (`iw-ai-log`) |

## Closing a change (the closing tasks in `tasks.md`)

Everything lands in the same PR, before archiving, because nothing goes straight to `main` and there is no "after merge" step:

1. Update docs per the table above, the `.docs/status/` file for the directories you changed (state, active changes, blockers), and the ADR for any hard-to-reverse choice the change made.
2. Add the log row with `iw-ai-log`.
3. Run `docs-check` (below) and fix each finding at its source.

Then `iw-pr-review`, then `/openspec-archive-change` as the last commit (see `openspec/config.yaml`).

## Writing rules

- Verify a claim against the code before writing it; a doc that is wrong is worse than a missing one.
- Link to the owning doc and section instead of copying text. Use repo-relative paths.
- The hand-in README is minimal: Quick Start, hardware requirements, per-service config. No marketing prose, no filler (the jury penalises it).
- English everywhere except user-facing dashboard text.

## ADRs

1. Copy `.docs/decisions/0000-template.md` to the next free number in your range (Adam `01xx`, Kacper `02xx`, Damian `03xx`, so three people never pick the same number), named `NNNN-short-title.md`.
2. The agent writes the whole ADR: Context, Options and Evidence (benchmarks, the real API read from the installed package, links), the **Decision**, and a rationale that cites that evidence; never invent a "why". Commit it with `Status: accepted`; it takes effect when the human approves and merges the PR (the human rejects it by requesting changes in review).
3. Add the file to the table in `.docs/decisions/README.md` (the checker fails otherwise) and remove it from the candidate list.
4. After the PR merges, do not edit it. A later decision supersedes it with a new ADR that links the old one.

## Check

```bash
node .claude/skills/iw-docs-update/scripts/docs-check.mjs
node --test ".claude/skills/iw-docs-update/scripts/*.test.mjs"   # only if the script changed
```

It fails on a broken relative link or backticked `.md` path, an ADR missing from the index, a service directory without `CLAUDE.md` or without a `/<dir>/` line in `.github/CODEOWNERS`, and a per-person ownership statement in a live doc (link `CODEOWNERS` instead, [ADR 0211](../../../.docs/decisions/0211-codeowners-single-source.md)). Fix each finding at its source; don't silence it. The service list is `SERVICE_DIRS` in the script; update it when the team adds a directory.
