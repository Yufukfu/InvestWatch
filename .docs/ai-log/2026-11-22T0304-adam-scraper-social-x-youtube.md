---
when: Sun ~03:00
who: Adam
---

## What was done with AI

Had Claude Code implement `scraper-social-x-youtube` (X over Scweet from the home IP, YouTube through our fetch layer, transcripts through a residential proxy) from a saved session file, one task group at a time: failing test first, a scripted mutation check (19 to 20 mutations per logic group, all caught), commit, then an `iw-reviewer` subagent on a pinned range, with each finding checked against the code before acting. Adam supplied the throwaway-account cookies and the proxy list through an untracked `.env` and had the agent run the first live run on the test stack.

## Outcome / lesson

Review caught one blocking defect the unit tests missed: the consent cookie was set on a per-request identity that a shared session ignores, so it never reached the wire; the fix was proven on the wire and in a live probe, not with stubs. A second review question (does the transcript library set a timeout?) turned out to be a real gap and got a bound. The full suite caught an HTTP-client import the project forbids in social modules. A stale baked test image made a mutated seed look like a real failure: rebuild the image after changing files baked into it. The per-new-file fact-gate hook added friction but no wrong output. The live run showed one 80,000-character transcript, which the spec does not cap.
