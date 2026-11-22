---
when: Sat ~13:50
who: Adam
---

## What was done with AI

Had Claude Code adapt the Neopadel SDLC (keep/leave table first): OpenSpec, `iw-*` skills, a tested `git-guard` hook, SDLC and review docs. Then ran a fresh reviewer agent on the whole PR for team usability

## Outcome / lesson

PR #1. The independent review found real gaps the author missed (hook blind to `git add && git commit`, `git push origin HEAD` allowed on main, dependency on a personal plugin, contradictory sizing text, merge-conflict hot spots); all fixed, with the hook changes test-first
