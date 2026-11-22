---
when: Sat ~23:15
who: Kacper
---

## What was done with AI

Claude Code planned and applied `calibration-panel` (slider over calibration points, precision/recall chart, explicit global threshold save) stacked on `realtime-alerts`, then drove the demo script in headless Chrome against the mock: M2 0.50 to 0.90, save, check the risk levels, restore 0.50

## Outcome / lesson

Mutation checks found 5 survivors, each a missing test case: a tie in the nearest-point search, a `labeled_samples` 0 case hidden by an index of -1, a confirmation shown before saving, a threshold changed from elsewhere, and a picked threshold that is gone from the curve. The browser run found a clipped 100% axis label and overlapping markers, which jsdom cannot show. The 0.5 to 0.7 step in the demo script changes no M2 risk level on the mock data (scores 0.86/0.74/0.12), so the demo should use 0.9 or real data
