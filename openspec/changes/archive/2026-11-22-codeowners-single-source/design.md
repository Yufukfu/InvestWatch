# Design

## Context

See proposal.md (Why). `docs-check.mjs` (`.claude/skills/iw-docs-update/scripts/`) walks every `.md` except archived changes and the OpenSpec skill symlinks, and CI runs it in the `Specs and hooks` job. Its test file (`docs-check.test.mjs`) builds fixture trees, so the new rules can be written test-first. The handles in `CODEOWNERS` are `hen68` (Adam), `kacpermalczyk` (Kacper) and `Yufukfu` (Damian).

## Goals / Non-Goals

**Goals:**
- One file answers "who owns X": `.github/CODEOWNERS`.
- A deterministic check stops ownership from creeping back into prose.

**Non-Goals:**
- Required code-owner review (a repo setting).
- Rewriting history: ADRs, the AI log and archived changes keep their names.
- Removing names that describe work or a person rather than ownership, for example "Scraper (Adam), insert a document" in `api/README.md`, "Kacper's review of PR #35" or "(Adam, PR #48)" in a code comment.

## Decisions

1. **Shared paths stay without an owner.** The alternative was a `* @all three` fallback. It was rejected because almost every PR touches a shared file (each PR updates a `.docs/status/` file), so GitHub would request the other two on nearly every PR, and every `iw-watch --review-requested` runner would review it. The user chose this in the session. This also keeps the PR #48 test "infra/ is shared: no owner" valid.
2. **The replacement text is a link, not a restated mapping.** A service `CLAUDE.md` title becomes `# scraper` followed by "Owners: `.github/CODEOWNERS`" as a relative link. The root `CLAUDE.md` and `README.md` tables keep directory and role and drop the owner column. `.docs/STATUS.md` maps status files to directories, not people.
3. **The ownership check uses patterns on live docs.** The patterns are `owner(s)`/`owned by`/`maintained by` followed by a name, `<Name> owns <module>`, `<Name>'s module`, a lowercase module name (`scraper`, `analytics`, `api`, `web`, `contracts`, `infra`, `dashboard`) followed by `(<Name>)` or `` `dir/` <Name> ``, and a table header with an `Owner` column. The names come from a list in the script. Lowercase only, so the prose "Scraper (Adam), insert a document" passes. It skips the numbered ADR files (`.docs/decisions/NNNN-*.md`; the index `README.md` is a live doc), `.docs/ai-workflow.md`, `openspec/changes/` (in-flight proposals, archived later and skipped there too) and spec scenario steps (`- **GIVEN**`/`**WHEN**`/`**THEN**`/`**AND**`), which are hypothetical examples. Besides the `.md` files it reads `openspec/config.yaml` and each `compose.yaml` at the root and in a module directory. A total ban on the names was rejected: it fails on log rows and review credits.
4. **The `CODEOWNERS` coverage check is structural.** For each existing directory in `SERVICE_DIRS`, a non-comment line `/<dir>/` must exist with at least one `@handle` (`@login` or `@org/team`). `infra/` is exempt because it is shared. No GitHub call: docs-check has no network.
5. **The `web-foundation` purpose line is edited by hand.** A purpose is not a requirement, so no delta can change it.
6. **`infra/` status stays in `.docs/status/dashboard.md`.** A status file covers directories and is no ownership claim once the names are gone, so no new file is needed. Its header says "whoever changes `infra/` updates its section".
7. **ADR 0211** (the next free number in Kacper's `02xx` range, 0208 is taken). It links 0202 and 0205 as partly superseded.

## Risks / Trade-offs

- [The pattern check misses a new wording, such as "Adam is responsible for `scraper/`"] → The tests cover the forms found today. A miss is a doc bug, not a behaviour change, and review still sees it.
- [The pattern check flags a legitimate sentence] → Reword it. There is no escape flag, which keeps the check simple.
- [A handle in `CODEOWNERS` goes stale, for example after an account rename] → GitHub shows "unknown owner" on the file in the web UI.

## Migration Plan

Docs plus one check, one PR. Rollback is reverting the PR.
