---
when: Sun ~00:30
who: Adam
---

## What was done with AI

Had Claude Code run the X and YouTube collector R&D (ADR 0109): robots.txt reads, Playwright, our own fetch layer, yt-dlp with a PO-token server and datacenter and residential proxies, plus a research subagent for transcripts; Adam supplied throwaway-account cookies through an untracked `.env` and recorded the robots.txt and login exception.

## Outcome / lesson

X timeline and YouTube metadata work; YouTube transcripts work through audio plus local Whisper but not through the caption URL (429 from the home IP). Lessons: the agent's proxy-redaction regex missed the `host:port:user:pass` format and printed a credential once (local only); a permission classifier denied a cookie-authenticated API probe until retried, so the action that needs a private API is better pre-agreed.
