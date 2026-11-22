---
when: Sun ~03:40
who: Kacper
---

## What was done with AI

The first automatic `ci.yml` run on a PR (#125, run 44975496928) failed `iw-watch` tests 183-185 with "Author identity unknown" and two follow-on assertion errors. Claude Code reproduced it locally by running the suite with the developer's git config ignored and identity guessing off, and found 8 failing tests. The fix gives `run.test.mjs` a fixed, hermetic git identity.

## Outcome / lesson

Branch `chore/iw-watch-ci-tests`.
- **Cause:** the tests gave identity only to their own `git -c user.name=...` calls. The runner's merge commit (`lib/worktree.mjs`) used the machine's identity: macOS guesses one from the host name, and a `~/.gitconfig` supplies one, so every laptop was green. A Linux runner has neither.
- **Fix:** set the identity env, ignore global and system git config, and turn on `user.useConfigOnly` for the test process.
- **Proof:** a mutant without the identity now fails the same 8 tests on a Mac (`mutations: 1 tried, 1 caught`).

The first fix attempt still passed that mutant, because the identity in `~/.gitconfig` hid it. Lesson: a test that touches git must ignore the developer's git config, or CI is the first place it runs clean.
