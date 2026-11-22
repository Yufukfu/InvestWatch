# Tasks

## 1. The docs-check rules

- [x] 1.1 Failing tests first in `.claude/skills/iw-docs-update/scripts/docs-check.test.mjs`. Cases: a service directory with no `.github/CODEOWNERS`; a `CODEOWNERS` missing `/scraper/`; a `/scraper/` line with no `@handle`; `infra/` without a line passes; a live doc with `# scraper (Adam's module)`, `**Owner:** Damian`, `` `infra/` (owner Kacper) ``, `owned by Kacper`, `` `scraper/` Adam `` and an `| Owner |` column; the same strings in `.docs/decisions/`, `.docs/ai-workflow.md` and `openspec/changes/`, which pass; "Scraper (Adam), insert a document" and a `- **GIVEN** ... owned by Damian` scenario step, which pass; `owner Damian` in `api/compose.yaml` and `openspec/config.yaml`, which fail. Verify with `node --test .claude/skills/iw-docs-update/scripts/` (the new cases fail).
- [x] 1.2 Implement both rules in `docs-check.mjs` and update its header comment. Verify: `node --test` passes.
- [x] 1.3 Mutation check (iw-commit-cycle step 3) on the two rules. `mutations: 16 tried, 16 caught`. On the first run 4 survived. Three were missing cases, and a test was added for each: a trailing-comment owner, `'s module` on its own, the module-name lookbehind. The fourth showed that two parts of the `<dir> (<Name>)` pattern added nothing: the optional word before `(`, because `dashboard` is a module word, and `owner ` inside the brackets, because the `owner <Name>` pattern already matches it. Both were removed, which also stops "scraper part (Adam)" in a milestone row from being flagged.

## 2. Remove ownership statements from live docs

- [ ] 2.1 `.github/CODEOWNERS` header: it is the source of truth, shared areas have no owner, and it no longer points at `.docs/STATUS.md`.
- [ ] 2.2 Root `CLAUDE.md` and `README.md`: drop the owner columns and the "confirm with Kacper" layout rule (a new top-level directory needs the whole team), link `CODEOWNERS`.
- [ ] 2.3 Service docs: titles and `Owner:` lines in the `CLAUDE.md` and `README.md` of `scraper/`, `analytics/`, `api/`, `contracts/`, `web/` and `infra/`; `web/CLAUDE.md`'s "Kacper also defines the repository structure"; `infra/README.md`; the module `compose.yaml` headers; `infra/postgres/init/01-app-role.sh`; `.claude/rules/web-dashboard.md`.
- [ ] 2.4 Process docs: `.claude/SDLC.md`, `openspec/config.yaml`, `.docs/integration-plan.md` §1, `.docs/analytics-plan.md`, `.docs/INDEX.md` (a "Who owns X?" route to `CODEOWNERS`), `contracts/README.md`, and the `web-foundation` spec purpose.
- [ ] 2.5 Status: `.docs/STATUS.md` maps files to directories only and loses the layout rule; `.docs/status/*.md` titles without names. Verify: `docs-check` exits 0 and `openspec validate --specs --strict` passes.
- [ ] 2.6 Mutation check: `mutations: n/a, docs-only group; the guard is docs-check from group 1`.

## 3. Closing

- [ ] 3.1 `iw-docs-update`: ADR `.docs/decisions/0211-codeowners-single-source.md` (partly supersedes 0202 and 0205), listed in `.docs/decisions/README.md`; `.docs/status/dashboard.md` updated; `iw-ai-log` row. Verify: `docs-check` exits 0.
- [ ] 3.2 Run `iw-pr-review` and fix real findings.

## Workflow follow-up

- `/openspec-archive-change` as the last commit, then push `chore/codeowners-single-source` and open the PR.
