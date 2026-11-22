---
when: Sat 17:55
who: Kacper
---

## What was done with AI

Kacper asked Claude Code to add lint and typecheck to CI (a gap hen68 found: the layering guard had only been checked through `npm test`); done as small change `ci-lint-typecheck`, verified by running the chain locally with a deliberate `console.log`

## Outcome / lesson

Not verified on GitHub Actions until the workflow runs; CI is advisory (SDLC stage 8)
