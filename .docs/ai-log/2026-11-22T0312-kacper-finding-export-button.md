---
when: Sun 03:12
who: Kacper
---

## What was done with AI

Issue #70, web part: an agent read the api PR #104 and mock PR #109, chose a plain link to the printable export (`?format=html`) built in the data hook from `VITE_API_BASE_URL`, regenerated the web contract snapshot for 1.2.0 (it was stale), and wrote the failing tests first (hook URL, link shown/hidden, untrusted-text link list), then the `Eksportuj` link in the detail header. One coordinating agent ran several issue agents in parallel worktrees.

## Outcome / lesson

Change `finding-export-button`. While listing mutants the agent saw that the first "no link" assertions, which queried by role, could not catch a dropped `exportUrl` guard: an `<a>` without `href` has no link role. The negative test was changed to query by text before the mutants ran (6 mutants, 6 caught). The iw-reviewer pass (security: yes) found nothing blocking. Lesson: assert absence by text, not by role, when the element could render without the attribute that gives it the role.
