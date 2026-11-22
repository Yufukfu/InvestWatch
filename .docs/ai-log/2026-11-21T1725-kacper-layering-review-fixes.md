---
when: Sat 17:25
who: Kacper
---

## What was done with AI

Fixed hen68's review of PR #12 through a second small OpenSpec change (`layering-review-fixes`): reproduced the holes first (nested component folders, `.tsx` extension, package subpaths), widened the lint patterns, added a test that lints the real components, then fixed the label fallback and the data-layer-imports-component direction and closed the test gaps

## Outcome / lesson

The first change claimed "the layering is a CI check" while CI only runs `npm test`, and the agent had tested the config on synthetic files only; the reviewer found both by trying a real violation. Mutation checks again found missing cases (4 of 14 pattern mutants survived until bare-form cases were added)
