---
when: Sun ~06:00
who: Adam
---

## What was done with AI

The PR #137 review said text fields lose their only visible cue when the resting border drops below 3:1, and offered a compromise. The agent did not apply it on its own because it reversed a choice the user had made; it asked, the user answered "as you suggest", and a small change (`dashboard-field-borders`) put the 3:1 border back on input, select and textarea while buttons and chips stay soft.

## Outcome / lesson

Mutation check 4 tried, 4 caught (a first script died on a bad anchor after two mutants; the other two were rerun with exact anchors and the file hash compared). No separate reviewer: three rules switched to an existing token under a style test.
