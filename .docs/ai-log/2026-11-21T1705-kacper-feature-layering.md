---
when: Sat 17:05
who: Kacper
---

## What was done with AI

Had Claude Code apply ADR 0204 through OpenSpec change `feature-layering`: lint guard first (oxlint `no-restricted-imports` on components, tested by running the real config), then health, summary and findings split into data hook, props-only component and page, each test-first with a mutation check

## Outcome / lesson

Two process slips caught by the checks, not by the agent: it committed the lint test without running `tsc` (Node types missing in the browser tsconfig), and its first mutation run on findings was void because the baseline was already red from a test bug. The mutation step now starts from a green baseline; one health mutant survived and led to an extra test for a response without `status`
