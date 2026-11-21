# InvestWatch code review bar

Criteria only. Stages are in `SDLC.md`, the commands in `.claude/skills/iw-pr-review/SKILL.md`, the dispatch steps in `.claude/skills/iw-commit-cycle/SKILL.md`. Review effort scales with blast radius, not with who wrote the code.

## Tiers

| Situation | Review |
|---|---|
| Each task group during implementation | `iw-reviewer` on a pinned range (once per task group or before a push) |
| Whole branch, as the closing review task | `iw-reviewer` on `merge-base..HEAD` (`/code-review` is the fallback) |
| Contract change, credentials, proxies, outbound requests from stored URLs, prompts built from scraped text | add a second pass with `focus: security` |
| High-risk diff, optional | a second reviewer from another model family (below) |

`ecc:code-reviewer` and `ecc:security-reviewer` are drop-in equivalents for teammates who have the ECC plugin; nothing depends on them. Per-commit review runs in its own session each time (fresh agent, no carry-over). On a PR, a teammate's review comments are handled by the author: clarify unclear items before changing code, no performative agreement.

## What "ready" means, in order

1. Deterministic checks green after the last code edit (commands in `iw-pr-review`): tests, lint, types, a mutation-check line per task group, `openspec validate`, `docs-check`, dependency audit, and `docker compose up` once a compose file exists.
2. A reviewer ran on the pinned range, with the security pass where the table says so.
3. **Every finding verified against the code** before acting: real ones fixed whatever the severity, false ones rejected with a one-line evidence note. After 3 rounds on one group, stop and ask the human.
4. No debug output left (`console.log` in JS/TS is hook-blocked; Python uses the logger, checked in review) and no `.env` or credentials tracked.
5. Every out-of-scope finding and every "declined to judge" item has a disposition in `follow-ups.md`.
6. The PR body names every behaviour change a teammate would notice, one line each, and any `IW_*` escape that was used; it is re-checked after any fix push.
7. A human gave a fresh go-ahead to push and to open the PR.

## Signals worth checking

- Scope-narrowing words ("only", "for now", an untracked TODO) in a diff or PR body often hide a gap.
- A test that cannot fail: name the production change that would turn it red, and ask for the group's mutation-check line. A mock asserted only as "called" proves nothing.
- Scraper traps: empty `text` saved on a parse failure, a Chrome UA with a non-Chrome TLS profile, credentials in logs, a stored URL fetched without a domain allow-list.

## Optional: different model family

For a high-risk diff, ask a second reviewer from another family (for example Codex or Gemini CLI) with the same pinned range and require a typed verdict per finding: `AGREE`, `DISAGREE_EVIDENCE` (cites code) or `DISAGREE_CONCERN`. Act on the verdicts, not on prose. Development-time aid only; the shipped system uses open-source models and no paid APIs. Not set up yet; add a skill when the team picks the tool.

Hard rules (push, `--force`, amend, ADRs) are in `CLAUDE.md`.
