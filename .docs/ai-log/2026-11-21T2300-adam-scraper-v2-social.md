---
when: Sat ~23:00
who: Adam
---

## What was done with AI

Had Claude Code implement `scraper-v2-social` (first social platform, Telegram) from the OpenSpec change: cold-read the spec against the code, researched five platforms through our own fetch layer for ADR 0103, then test-first per task group (parser on saved real pages, collector registry, post identity hash, social branch of `run_source` with bounded paging, seeds), a mutation check per group and an `iw-reviewer` pass per group, in a worktree stacked on the open orchestration PR

## Outcome / lesson

The agent's first parser tests were mirrored from the parser; expected values were re-read from the saved pages instead. Mutation checks found four surviving mutants in group 1 and two in group 2, each closed with a test. Review caught a real flaw: the older-posts link came from the page and was followed on any allowed host; it is now pinned to the same channel. Issue 34 changed the hash input (canonical URL) and PR 41 moved the author to a trusted argument; both were folded into the spec and code. The agent should have looked at the open PRs earlier. The human chose Telegram and the stacked-PR approach; the brief's Facebook, Instagram and TikTok stay uncovered and say so
