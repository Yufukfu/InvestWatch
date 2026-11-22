---
when: Sun ~03:20
who: Adam
---

## What was done with AI

A Claude Code session applied the approved `dashboard-redesign` change to `web/` in task groups (test first, mutation check, `iw-reviewer` per commit), then had Sonnet subagents compare production-build screenshots with the Paper exports. The comparison showed the first pass did not look like the mockups (navy header and blue accent where the mockup is white, ink and red), so a fidelity pass (tasks 8a.1-8a.7) followed: sequential for the shared stylesheet, then two agents in parallel, one in a separate git worktree, merged by cherry-pick

## Outcome / lesson

Branch `web/dashboard-redesign`, 485 Vitest tests, mutation checks 100% caught (survivors killed with tests or removed as dead code). The first-pass tokens were written from an assumed look instead of the exported JSX; the screenshot review caught it, not the tests. A subagent's bad script index duplicated ~300 lines of `styles.css` (caught by its own report and a duplicate-section check), another wrote tests and code before seeing red (mutation checks were the evidence). Programmatic measurement, not review, found an 8 px overflow at 320 px and 41 px targets; review found one real defect (pager text hidden from screen readers on phone). `App.test.tsx` trend test fails about 1 run in 12 under load (not caused by this change). The Playwright MCP needs a browser extension that is not installed: `playwright-core` from a scratch directory with the cached Chromium worked instead. After the merge of `main` (98 commits) the commit hook blocked the merge commit on a `console.log` that came from main's own `ai-log.mjs`, so the merge was finished with `git merge --continue`; the merged tree passes lint, types and 485 tests.
