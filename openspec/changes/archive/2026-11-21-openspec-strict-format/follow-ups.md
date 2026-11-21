# Follow-ups

| # | Item | Disposition |
|---|---|---|
| 1 | `analytics-llm-p0` fails 2.1.1 strict on its own deltas: 17 ADDED/MODIFIED requirements over 500 characters. After merging `main`, its MODIFIED `Rule catalogue`, `R3 …` and `M2 finding assembly` replace the blocks changed here, so keep the `**AND**` lines this change added (or their content) when shortening them. | fix-here, on `analytics/analytics-llm-p0` (Damian) |
| 2 | `analytics-m1-m3` fails 2.1.1 strict: 12 requirements over 500 characters, and two ERRORs where MODIFIED `Routing to modules` and `M2 finding assembly` omit existing scenarios (`Third-party post`, `Unmatched firm on its own page`). The branch has since archived the change, so the fix lands in its `openspec/specs/` and archive. Its MODIFIED `M2 finding assembly` also replaces the block changed here: keep the `**AND**` lines this change added. | fix-here, on `analytics/analytics-m1-m3` (Damian) |
| 3 | Some local CLIs are still OpenSpec 1.2.0, which has no length check, so local validation passes while CI fails. `CLAUDE.md` already pins 2.1.1 (`npm i -g @fission-ai/openspec@2.1.1`). | docs (already documented; reinstall locally) |
