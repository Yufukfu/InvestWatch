---
when: Sun 03:12
who: Kacper
---

## What was done with AI

An issue agent took @hen68's #91 review follow-ups (issue #99) through a small OpenSpec change: failing tests first, then a shared `isolate()` helper (U+2068/U+2069) for the toast `aria-label`s and the live-region announcement, and `dir="auto"` on the StatusEditor server detail.

## Outcome / lesson

Change `bidi-isolate-a11y`, issue #99. 9 of 9 mutants caught; `iw-reviewer` found nothing blocking. One slip caught before commit: the agent's shell heredoc wrote the isolate characters into `bidi.ts` and its test as raw invisible code points; a scan for bidi controls in the diff found them and they were replaced with `\u2068`/`\u2069` escapes, so the source has no hidden bidi characters. Not verified: a real screen reader announcing the isolated label.
