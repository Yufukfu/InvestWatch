# Follow-ups

Findings from `iw-reviewer` that were not fixed in the group's own commit, one disposition each.

| Source | Finding | Disposition |
|---|---|---|
| review groups 1-2 | `fixtures/pr-comments.json` looks hand-edited | `docs`: `fixtures/README.md` says which fixtures are saved `gh` output and which entries were added for the round-count tests |
| review groups 1-2 | `saveState` does not fsync, so power loss can lose the last write | `wont-fix`: the state is a cursor; losing one write repeats one item, and the round count also lives on GitHub (marker) |
| review groups 1-2 | Team owners (`@org/team`) cannot be issue assignees | `fix-here` in group 5 (owner-routed issues assign logins only) |
| review groups 1-2 | Relative `XDG_STATE_HOME`, default umask on the state dir | `wont-fix`: the state file is written 0600 and holds no secrets; drafts are reviewed in group 4 |
| review group 3 | An APPROVED review with a body counts as `address-review` work | `wont-fix`: "LGTM, nit: rename x" is worth handling; the round cap bounds it |
| review group 3 | Edited comments (`updated_at`) are not picked up again | `wont-fix` for v1: handled by event id; an edit is rare and visible to the human |
| review group 3 | `gh pr list --json files` may cut the file list at 100 | `fix-here` in group 5: the domain filter treats a list of 100 files as possibly incomplete |
| review group 3 | `review-requested:@me` may not match team review requests | `docs`: SKILL.md says it watches personal requests only |
