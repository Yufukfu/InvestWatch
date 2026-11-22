---
when: Sun ~05:40
who: Adam
---

## What was done with AI

PR #137 had conflicts with `main` and a teammate's AI-assisted review with three blocking points. The agent merged `main` (module switcher, export button, rescan notice, ADR number clash resolved by renumbering the font ADR to 0214), then fixed two points test-first in a small change: deep links without a hash now open the findings page, and the status shortcuts no longer discard an unsaved note. The third point (resting control borders below 3:1) contradicts what the user chose, so it was not changed and was put back to the user.

## Outcome / lesson

Mutation check 8 tried, 8 caught. The merge silently dropped `formatUtc` from `labels.ts` (git took this branch's deletion of neighbouring code while `main`'s new `RescanNotice` still used it); main's own tests caught it, not the conflict markers. Main's `getByLabelText('Status')` test had to follow the radio-pill editor. The deep-link fallback changed an existing test: a URL with filters now opens the findings page, so the triage test names the overview explicitly.
