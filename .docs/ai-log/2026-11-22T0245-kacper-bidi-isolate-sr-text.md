---
when: Sun ~02:45
who: Kacper
---

## What was done with AI

A Claude Code subagent took issue #99, the follow-ups from the review of PR #91: alert titles inside the toast `aria-label`s and the live announcement, and the status editor's server detail. It weighed `aria-labelledby` against U+2068/U+2069 (FSI/PDI) for the flat strings, chose FSI/PDI, wrote U+202E tests first (red on assertions, against an identity stub), then added a balancing `isolate()` helper and a scripted mutation check.

## Outcome / lesson

Change `bidi-isolate-sr-text`. `aria-labelledby` was rejected because the accessible name is flattened to plain text, which drops the `dir` isolation; FSI/PDI live in the string. A plain wrap is not enough: a PDI in the title would close the isolate early, so `isolate()` drops stray PDIs, closes isolates the title leaves open and turns paragraph separators into spaces. The file-writing tool turned some `\uXXXX` escapes into literal invisible bidi characters in the new source and tests (a Trojan Source pattern); a scan caught it and the characters were escaped again before the first code commit. Lesson: scan new files for literal bidi controls when a change is about bidi controls.
