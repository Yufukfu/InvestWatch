# InvestWatch code review bar

Criteria only. Stages are in `SDLC.md`, the commands in `.claude/skills/iw-pr-review/SKILL.md`, the dispatch steps in `.claude/skills/iw-commit-cycle/SKILL.md`. Review effort scales with blast radius, not with who wrote the code.

## What counts as a finding

Only a **blocking** defect: it is on a line the change adds or touches (or the change makes old code break), it has a concrete trigger (input or state → wrong result), and it is one of: wrong result or crash, data loss, a dropped failure path, a race, a security hole, a contract field wrong against `.docs/integration-plan.md`, a spec SHALL not implemented, or a test that cannot fail on the guard it pins. The full bar is in `.claude/agents/iw-reviewer.md`.

Style, naming, structure, "could be simpler", nice-to-have tests and pre-existing issues the change does not touch are **not** findings: reviewers don't report them and authors don't fix them. Anything a deterministic check covers is left to the check.

## Tiers (each range is reviewed once)

| Situation | Review |
|---|---|
| A task group with logic (guard, parser, rule, query, handler, contract) | `iw-reviewer` on that group's range only: `LAST_REVIEWED..HEAD` |
| Docs-only, config-only, pure rename, tests/fixtures that pin no guard | no LLM review; deterministic checks only |
| Whole branch, as the closing review task | one `iw-reviewer` pass on `merge-base..HEAD`, with `already-reported:` from the group reviews; it looks for cross-group and spec gaps, not a second line-by-line pass |
| Contract change, credentials, proxies, outbound requests from stored URLs, prompts built from scraped text | add `security: yes` to the same pass (one agent call, not two) |
| Fix commits after a review | `iw-reviewer` on the fix range only (`FIX_BASE..HEAD`), with `already-reported:` |
| High-risk diff, optional | a second reviewer from another model family (below) |

`ecc:code-reviewer` and `ecc:security-reviewer` are drop-in equivalents for teammates who have the ECC plugin; nothing depends on them. Every review is a fresh agent (no carry-over). Run the cheap deterministic checks before any LLM review: a red check is fixed first, not reviewed.

## Reviewing a teammate's PR

Post blocking items only, each with `file:line`, the trigger and the smallest fix. No nits section. If there is nothing blocking, approve. The author clarifies an unclear item before changing code; no performative agreement. A second round reviews only the fix commits.

## What "ready" means, in order

1. Deterministic checks green after the last code edit (commands in `iw-pr-review`): tests, lint, types, a mutation-check line per task group, `openspec validate`, `docs-check`, dependency audit, and `docker compose up` once a compose file exists.
2. The reviews the table asks for ran, each on its own range.
3. **Every finding verified against the code** before acting: real ones fixed, false ones rejected with a one-line evidence note. After 2 rounds on one range, stop and ask the human.
4. No debug output left (`console.log` in JS/TS is hook-blocked; Python `print` is grepped by `iw-pr-review`) and no `.env` or credentials tracked.
5. Every "out of scope but blocking elsewhere" finding has a disposition in `follow-ups.md`. "Could not check" items go in the PR body, not in `follow-ups.md`.
6. The PR body names every behaviour change a teammate would notice, one line each, and any `IW_*` escape that was used; it is re-checked after any fix push.
7. The push goes to the agent's own feature branch, never `main` and never with `--force`. A human approves and merges the PR; an agent does neither.

## Optional: different model family

For a high-risk diff, ask a second reviewer from another family (for example Codex or Gemini CLI) with the same pinned range and the bar above, and require a typed verdict per finding: `AGREE`, `DISAGREE_EVIDENCE` (cites code) or `DISAGREE_CONCERN`. Act on the verdicts, not on prose. Development-time aid only; the shipped system's own LLM use is set by ADR 0304 (`.docs/decisions/0304-llm-serving.md`). Not set up yet; add a skill when the team picks the tool.

Hard rules (push, `--force`, amend, ADRs) are in `CLAUDE.md`.
