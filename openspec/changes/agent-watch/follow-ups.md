# Follow-ups

Findings from `iw-reviewer` that were not fixed in the group's own commit, one disposition each.

| Source | Finding | Disposition |
|---|---|---|
| review groups 1-2 | `fixtures/pr-comments.json` looks hand-edited | `docs`: `fixtures/README.md` says which fixtures are saved `gh` output and which entries were added for the round-count tests |
| review groups 1-2 | `saveState` does not fsync, so power loss can lose the last write | `wont-fix`: the state is a cursor; losing one write repeats one item, and the round count also lives on GitHub (marker) |
| review groups 1-2 | Team owners (`@org/team`) cannot be issue assignees | `fix-here` in group 5 (owner-routed issues assign logins only) |
| review groups 1-2 | Relative `XDG_STATE_HOME`, default umask on the state dir | `wont-fix`: the state file is written 0600 and holds no secrets; drafts are reviewed in group 4 |
