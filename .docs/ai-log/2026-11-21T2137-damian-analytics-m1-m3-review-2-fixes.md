---
when: Sat ~21:37
who: Damian
---

## What was done with AI

Claude Code fixed Kacper's second review of PR #35 in `analytics-m1-m3-review-2-fixes` after merging #26's tip (9bd27e8): reproduced each item with a probe first (22 s for 1 MB in `registry.match`, M2 at 1.0 for a backslash URL and for a name-like TikTok handle), then failing test, fix and a scripted mutation check per group

## Outcome / lesson

Branch `analytics/analytics-m1-m3` (merge only). The mutation runner showed the ReDoS tests needed adversarial inputs that actually reach the pattern (a label in the negation text, an href body without `&`), and a growth check instead of a fixed budget; the 500-character requirement rule from #37 was met by moving overflow sentences into scenarios
