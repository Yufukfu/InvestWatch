# Follow-ups

Findings from `iw-reviewer` that were not fixed in the group's own commit, one disposition each.

| Source | Finding | Disposition |
|---|---|---|
| review groups 1-2 | `fixtures/pr-comments.json` looks hand-edited | `docs`: `.claude/skills/iw-watch/scripts/fixtures/README.md` says which fixtures are saved `gh` output and which entries were added for the round-count tests |
| review groups 1-2 | `saveState` does not fsync, so power loss can lose the last write | `wont-fix`: the state is a cursor; losing one write repeats one item, and the round count also lives on GitHub (marker) |
| review groups 1-2 | Team owners (`@org/team`) cannot be issue assignees | `fix-here` in group 5 (owner-routed issues assign logins only) |
| review groups 1-2 | Relative `XDG_STATE_HOME`, default umask on the state dir | `wont-fix`: the state file is written 0600 and holds no secrets; drafts are reviewed in group 4 |
| review group 3 | An APPROVED review with a body counts as `address-review` work | `wont-fix`: "LGTM, nit: rename x" is worth handling; the round cap bounds it |
| review group 3 | Edited comments (`updated_at`) are not picked up again | `wont-fix` for v1: handled by event id; an edit is rare and visible to the human |
| review group 3 | `gh pr list --json files` may cut the file list at 100 | `fix-here` in group 5: the domain filter treats a list of 100 files as possibly incomplete |
| review group 3 | `review-requested:@me` may not match team review requests | `docs`: SKILL.md says it watches personal requests only |
| review group 4 | A review checked out the PR head, so the PR's own .claude/ hooks would run | `fix-here`: base-branch working tree, PR head as `refs/iw/pr-<n>` (probe: project hooks run in an untrusted directory) |
| review group 4 | Project allow rules (`git push origin:*`, `gh pr create`) widen sessions, dry runs included | `fix-here`: per-session `--disallowedTools` for dry runs and reviews; probe: an untrusted clone's project allow rules are ignored anyway |
| review group 4 | Unscoped Read/Write/Edit and `gh --repo` | `fix-here`: `Read(./**)`, `Edit(./**)` (review: `Edit(./.iw-watch/**)`), denies for `.git/`, `.claude/`, `.env` and `gh * --repo *` |
| review group 4 | File paths outside the fence; "remove to retry" was false; `.iw-watch/` not ignored | `fix-here`: fenced and printable paths; blocked items kept and told once; `.git/info/exclude` |
| review group 4 | Test runners give a session on my own branch arbitrary code execution | `docs`: stated as the residual risk in design.md D4; only collaborators' text reaches such a session |
| review group 4 | `spawnSync` timeout can leave a session's child processes alive; `IWATCH_NOTIFY_CMD` splits on spaces | `wont-fix` for v1: SKILL.md says to point it at a script without spaces in its path |
| e2e on PR #39 | The first live run failed: `git clone --reference` checkout said "unable to parse commit" (stale commit-graph in the main clone), and the half-made clone then blocked every later run | `fix-here`: `-c core.commitGraph=false`, and a clone that fails while being made is removed; both pinned in `run.test.mjs` |
