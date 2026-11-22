---
when: Sat 16:17
who: Kacper
---

## What was done with AI

Asked Claude Code what the frontend architecture rules are; it found none beyond the props rule and that the existing components import generated hooks directly. Wrote ADR 0204 (feature data hooks as the boundary to the generated client, view models, presentational components) and extended the rule, comparing hooks, container components and the status quo against the code

## Outcome / lesson

The swap test decided it: `generated.ts` is RTK-specific, so with the status quo replacing RTK Query touches every component. Container components add a tree level without more isolation. The ADR records that the existing components are not moved yet: that is code, so it waits for an OpenSpec change Review of PR 11 then found the draft overstated what the code shows (store and test setup also import `generated.ts`, `HealthBadge` is 20 lines, container components compared too thinly) and that the layering had no lint enforcement; the ADR was rewritten with those facts
