---
when: Sun ~00:00
who: Kacper
---

## What was done with AI

Claude Code implemented `security-ci` (ADR 0209 in CI). It wrote a dependency-free pin test first, then `security.yml`: Gitleaks and OSV-Scanner as digest-pinned images run through `docker run`, plus `.gitleaks.toml`. It checked the allowlist against a scratch copy of the mock file with a credential-shaped line added. The first Actions run on PR #100 was the verification: all jobs green, including the first OSV-Scanner offline run on this repository.

## Outcome / lesson

PR #100.

- The design's top-level `[[allowlists]]` with `paths` and `condition = "AND"` passed the obvious check (2 hits down to 0), but it hid the planted line too: in Gitleaks v8.28.0 a top-level path skips the whole file. The entry moved to a rule-scoped `[[rules.allowlists]]`, which reports exactly the planted line.
- The runbook's worktree recipe (`-v "$PWD:$PWD"`) scanned 0 commits and still said "no leaks found" with exit 0, because Docker Desktop showed the same-path mount as empty. The CI step now fails on 0 commits scanned, and the runbook mounts at fixed paths.
- `iw-reviewer` found two real holes in the pin test, in two rounds:
  - images without a `/`
  - a second `docker run` on the same line
- The whole-branch review found a spec SHALL that OSV-Scanner could not meet: an npm severity exception that only `npm audit` applies.
- Kacper decided the offline scan must run before the merge. A manual run needs the workflow on `main`, so it runs on every PR that changes `security.yml`. The scans stay a visible but non-blocking check, watched in review: required checks need a paid plan or a public repo.

Lesson: test an allowlist by planting a secret it must still catch, not only by watching the known hits disappear.
