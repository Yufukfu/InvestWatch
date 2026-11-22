---
when: Sun ~00:30
who: Damian
---

## What was done with AI

A Claude Code side session did Damian's part of issue #33 (several findings per document): it drafted the OpenSpec change, the exact `openapi.yaml` diff, the 1.1.0 bump and the M1+M3 mock first, stopped for the team's OK on the post-freeze contract change, then applied three test-first task groups (contract + mocks, mock server, api) with a scripted mutation check each

## Outcome / lesson

Mutations 3/3, 3/3, 3/3. The new mock post broke an existing mock-server search test that assumed only Alfa-firm findings mention "Alfa Inwestycje"; it now searches a phrase found only in firm names. `IW_CONTRACT_CHANGE=1` used on the contract commit after the team's OK. Lesson: the iw-commit-cycle rule "no Co-Authored-By" conflicts with the harness attribution default; the repo rule wins
