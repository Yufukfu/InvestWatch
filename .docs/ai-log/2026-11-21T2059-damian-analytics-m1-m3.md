---
when: Sat ~20:59
who: Damian
---

## What was done with AI

Claude Code fixed Kacper's review of PR #35 (`analytics-m1-m3`) in `analytics-m1-m3-review-fixes`, with the coordinating session relaying Damian's rulings (narrowing the Polish-marker filter to foreign firms without a branch, ADR 0308 for the M3 gate). Each claim was reproduced with a probe before fixing; failing test first, a scripted mutation check per group

## Outcome / lesson

Branch `analytics/analytics-m1-m3` (merge only). The reviewer caught what the agents' own five per-group reviews missed: wording that stated a registry fact on fictional data, a bare `partner` label crossing the alert line, the platform named as advertiser, and the challenge's own M3 terms missing. Lesson: test outputs against the challenge text, not only against the spec written from it
