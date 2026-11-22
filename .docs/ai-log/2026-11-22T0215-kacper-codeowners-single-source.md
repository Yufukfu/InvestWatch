---
when: Sun ~01:45
who: Kacper
---

## What was done with AI

Kacper asked Claude Code to check whether code owners are written in one place after PR #48. The agent found the owners restated in about 25 live files. Five of them said Kacper owns `infra/`, although `CODEOWNERS` had no line for it. The agent then ran `codeowners-single-source`:
- two `docs-check` rules: every module has a `CODEOWNERS` owner, and no live doc names a path's owner;
- written test-first, with a scripted mutation check;
- the docs rewritten to link `CODEOWNERS`;
- ADR 0211.

After that the agent watched PR #95, fixed review comments and merged `main` each time it moved.

## Outcome / lesson

PR #95, branch `chore/codeowners-single-source`.

- **Planning.** The agent's first plan put all three of us on the shared paths. Before writing it, the agent read `iw-watch`'s `domainFilter` and saw that GitHub would then request two reviewers on almost every PR. It asked, and Kacper kept the shared paths unowned.
- **Mutation checks.** They found two redundant parts of one regex. Removing them also fixed a false positive ("scraper part (Adam)"). Later they found a test that had stopped guarding the module-name lookbehind.
- **Reviews.**
  - The `iw-reviewer` agent type was not registered in the session, so a general agent ran the reviews with its instructions.
  - The group review found two misses: the `platform` status title, and `compose.renderer.yaml`, which was skipped because only `compose.yaml` was read.
  - The whole-branch review found four places that still stated the old "own status file" and "Kacper's layout" rules.
  - Adam's review added `maintained by` and `<Name> owns <dir>`, and limited the ADR skip to numbered ADR files.
  - Damian's review found five nits, all verified and fixed: a PR credit in parentheses was flagged as ownership; the coverage rule didn't use GitHub's last-line-wins rule; a handle next to a module name wasn't caught; the scenario-step skip applied outside `openspec/specs/`; and "A 01xx".
- **Decision.** After Damian's review raised it, Kacper made Damian (`@Yufukfu`) the owner of `infra/`. ADR 0211 was amended to record it.
- **Result.** Last guard change: 18 mutants tried, 18 caught.
- **Process note.** `main` moved under the PR four times. In the last merge, PR #103 changed the AI log to one file per entry, so the old table row became this entry.
