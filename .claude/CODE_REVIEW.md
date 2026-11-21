# InvestWatch code review bar

Companion to `SDLC.md`. Review effort scales with blast radius, not with who wrote the code.

## Tiers

| Situation | Review |
|---|---|
| Every commit during implementation | `ecc:code-reviewer` on a pinned range (`iw-commit-cycle`) |
| Whole branch before the PR | `iw-pr-review`: `ecc:code-reviewer` or `/code-review` on `merge-base..HEAD` |
| Contract change, credentials, proxies, outbound requests from stored URLs, prompts built from scraped text | add `ecc:security-reviewer` |
| High-risk diff, optional | second reviewer from another model family (below) |

Per-commit review runs in its own session each time (fresh agent, no carry-over). On a team PR, a teammate's review comments are handled by the author: clarify unclear items before changing code, no performative agreement.

## Dispatching a reviewer

Always give it: the pinned `BASE..HEAD` range and worktree path, the path of the OpenSpec change (ask for plan compliance: missing, extra, misunderstood), and an instruction to list what it declined to judge and what it could not verify from the diff. The reviewer reads and reports; it does not edit, commit or spawn agents.

## What "ready" means, in order

1. Deterministic checks green after the last code edit: module tests, lint, types, `openspec validate --all --strict`, dependency audit, `docker compose up` for service changes.
2. Reviewer ran on the pinned range; path-selected extra reviewers ran.
3. **Every finding verified against the code** before acting: real ones fixed (whatever severity), false ones rejected with a one-line evidence note. After 3 rounds on a commit, stop and ask the human.
4. No debug output left: no `console.log` / `print`, no `.env` or credentials tracked.
5. Every out-of-scope finding has a disposition in `follow-ups.md`.
6. The PR body names every behaviour change a teammate would notice, one line each, and is re-checked after any fix push.
7. A human gave a fresh go-ahead to push and to open the PR.

## Signals worth checking

- Scope-narrowing words ("only", "for now", an untracked TODO) in a diff or PR body often hide a gap.
- A test that cannot fail: name the production change that would turn it red. Mocks asserted only as "called" prove nothing.
- Scraper traps: empty `text` saved on a parse failure, a Chrome UA with a non-Chrome TLS profile, credentials in logs, a stored URL fetched without a domain allow-list.

## Optional: different model family

For a high-risk diff, ask a second reviewer from a different family (for example Codex or Gemini CLI) with the same pinned range, and require a typed verdict per finding: `AGREE`, `DISAGREE_EVIDENCE` (cites code) or `DISAGREE_CONCERN`. Act on the verdicts, not on prose. This is a development-time aid only; the shipped system uses open-source models and no paid APIs. Not set up yet; add a skill when the team picks the tool.

## Hard rules, every tier

No push, PR or review submission without a fresh go-ahead. No `--force`, no amending a pushed commit. No auto-merged ADRs.
