# 0212. AI log: one file per entry

- Status: accepted
- Date: 2026-11-22
- Deciders: agent-written; effective when the human merges the PR

## Context

The AI log (the jury's evidence for the "AI-assisted process" criterion) was one Markdown table at the bottom of `.docs/ai-workflow.md`. The closing tasks of every OpenSpec change add a row to it (`iw-ai-log`), so nearly every PR edits the same last lines of the same file: 233 commits on `origin/main` touched it. Two PRs that each append a row conflict at the end of the table.

`.gitattributes` set `merge=union` on the file to keep both sides' rows. That did not solve it, for two reasons:

1. GitHub does not apply `.gitattributes` merge drivers when it checks whether a PR can merge, so the PR still shows a conflict and someone has to merge `main` locally.
2. A union merge keeps both versions of an edited line. The log had a duplicated row this way: the `analytics-eval-calibration` row appeared twice, the second copy with a sentence added.

[ADR 0205](0205-status-per-domain.md) fixed the same problem for `.docs/STATUS.md` by splitting the file.

## Options considered

1. **Keep the table and `merge=union`.** Nothing to migrate, but the PR conflicts on GitHub and the duplicated rows stay.
2. **One log file per person.** Conflicts between people go away, but one person's parallel worktrees still append to the same file.
3. **One file per entry in `.docs/ai-log/`**, with a timestamp at the start of the file name, and a script that renders the table on demand. Two PRs never touch the same path, so a conflict is impossible. The jury view comes from `render`, and `check` in CI keeps entries well-formed.

## Decision

Option 3. Each entry is `.docs/ai-log/YYYY-MM-DDTHHMM-<adam|kacper|damian>-<slug>.md` with `when:` and `who:` front matter and two sections, `## What was done with AI` and `## Outcome / lesson` (the old table's columns). `.claude/skills/iw-ai-log/scripts/ai-log.mjs` has `new` (creates the file from the template), `check` (run in CI, also rejects a leftover `TODO`) and `render` (the full table, oldest first). The 83 existing rows became 82 files with the text unchanged: the duplicated row was kept once, in its longer version, and the old label `A` was changed to `Adam`. The `merge=union` line is removed from `.gitattributes`.

## Consequences

- A PR that adds a log entry adds one new file and edits nothing shared.
- `.docs/ai-workflow.md` now holds only the process description, so it changes only when the process changes.
- An open PR that still adds a table row gets one last conflict. To resolve it, take `main`'s `.docs/ai-workflow.md` and move the row into a file with `ai-log.mjs new`.
- Readers who want one page run `render`; for the hand-in its output can be pasted into the PDF.
