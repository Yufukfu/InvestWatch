---
name: iw-docs-update
description: Use before any commit or PR that changes behaviour, a contract, a service's config or run steps, or a decision, and after every merge. Says which doc to update for which change, how ADRs are drafted, and runs the deterministic docs-check. Not for editing openspec/specs by hand (archive does that).
---

# iw-docs-update

Docs hold the logic; `CLAUDE.md` files stay short and point at them. Update docs in the same PR as the code, then run the check.

## If you changed X, update Y

| Change | Update |
|---|---|
| A contract (`ScrapedDocument`, `Finding`, a REST route, an event) | `contracts/` schema and mocks, `doc/integration-plan.md` (§3-§6), the OpenSpec change's spec delta, consumers' tests. Needs the whole team and a version bump. |
| A service's run steps, env vars or definition of done | that service's `CLAUDE.md`, `.env.example`, and the README Quick Start once it exists |
| A new service directory | its own `CLAUDE.md`, a row in the root `CLAUDE.md` services table, a row in `doc/INDEX.md` |
| System behaviour | the OpenSpec change (`/openspec-archive-change` merges it into `openspec/specs/`). Never hand-edit `openspec/specs/`. |
| A milestone moved, a blocker appeared or cleared | `doc/STATUS.md` |
| The process, a skill or a hook | `.claude/SDLC.md` or `.claude/CODE_REVIEW.md`, and `doc/ai-workflow.md` |
| A hard-to-reverse choice | an ADR (below) |
| A merged PR or milestone | one row in the Log table of `doc/ai-workflow.md` (`iw-ai-log`) |

## Writing rules

- Verify a claim against the code before writing it; a doc that is wrong is worse than a missing one.
- Link to the owning doc and section instead of copying text. Use repo-relative paths.
- The hand-in README is minimal: Quick Start, hardware requirements, per-service config. No marketing prose, no filler (the jury penalises it).
- English everywhere except user-facing dashboard text.

## ADRs

1. Copy `doc/decisions/0000-template.md` to the next number, `NNNN-short-title.md`.
2. An agent may fill Context, Options and Evidence (benchmarks, the real API read from the installed package, links). Set `Status: proposed`. Leave **Decision** and its rationale for the human to write; never invent a "why".
3. Add the file to the table in `doc/decisions/README.md` (the checker fails otherwise) and remove it from the candidate list.
4. After the human accepts it, do not edit it. A later decision supersedes it with a new ADR that links the old one.

## Check

```bash
node .claude/skills/iw-docs-update/scripts/docs-check.mjs
node --test ".claude/skills/iw-docs-update/scripts/*.test.mjs"   # only if the script changed
```

It fails on a broken relative link or backticked `.md` path, an ADR missing from the index, and a service directory without `CLAUDE.md`. Fix each finding at its source; don't silence it. The service list is `SERVICE_DIRS` in the script; update it if B changes the layout.
