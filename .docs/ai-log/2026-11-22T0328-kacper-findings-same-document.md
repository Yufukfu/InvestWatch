---
when: Sun ~03:00
who: Kacper
---

## What was done with AI

Issue #33 (one post gives M1 and M3 findings shown as unrelated rows). Claude Code ran the OpenSpec change `findings-same-document` with `iw-commit-cycle`: group 1 (source host in rows, `documentId` in the view models) before the contract existed, group 2 (module switcher in the detail on `GET /findings?document_id=…`) after Damian's contract 1.1.0 merged. Tests first per group, then hand mutants applied by a script that asserts the snippet and restores the file, then a reviewer agent on the group's commit range.

## Outcome / lesson

Branch `web/findings-same-document`. Mutations: group 1 11/11, group 2 20/20 after adding tests for three survivors. One survivor exposed a real bug: the switcher's focus effect ran once at mount, before the sibling list arrived, so focus after a switch only worked because the siblings were cached; fixed by focusing once when the switcher is first shown. An interrupted session left a mutant in the working tree twice (`documentId: f.id`, the select guard); both were found by checking the original snippets before continuing, which is why the cycle's "restore and verify" step matters. The `iw-reviewer` agent did not load because the session started outside the repo; a general-purpose agent with its definition was used instead. Headless Chrome does not start in the agent environment, so the 375/1280 px check is left to the human on the PR.
