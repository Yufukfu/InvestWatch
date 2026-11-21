# Follow-ups

Review items of PR #15 not fixed in code here, and findings made while fixing them. One disposition each.

| # | Source | Item | Disposition |
|---|---|---|---|
| 1 | Kacper's review, item 7 | `unpublished_documents` takes no `FOR UPDATE SKIP LOCKED`, so two sweepers, or a sweeper and a retrying publisher, can announce one document twice | docs (`api/README.md`: `iw:documents` consumers are idempotent on `document.id`; the analytics upsert already is). Locking the sweep is a `new-item` for the scraper if it ever runs more than one sweeper |
| 2 | Kacper's review, item 12 | no history of status changes: `findings.status` and the re-scan upsert overwrite in place, while the challenge asks to record status changes | new-item (change `api-v1`: a `finding_status_history` table written by `PATCH /findings/{id}`, as a new revision) |
| 3 | Kacper's review, item 13 | no CI runs the api tests; the green result rests on local runs against `postgres:17-alpine` | docs (said in the PR body; CI is advisory for the hackathon, `.claude/SDLC.md` stage 8) |
| 4 | Kacper's review, item 14 | `openspec/changes/api-v1/` ships in PR #15 | docs (it stays as a proposal only, not applied and not for review here; the PR body says so) |
| 5 | enum test, this change | CHECK constraints created by `0001` are named twice over (`ck_documents_ck_documents_platform`): `env.py` passes `tables.metadata`, whose naming convention prefixes names that `0001` already wrote in full. `0003` uses the short name, so its constraint is `ck_documents_text_not_empty`. Only CHECKs are affected (pk, fk, uq and ix names are as written) | new-item (rename the CHECKs in a later revision; until then error-message mapping in `api-v1` must use the doubled names, and new revisions pass short CHECK names) |
| 6 | compose, this change | `api/compose.yaml` cannot run alone: it uses `postgres` and the `data` network from `infra/compose.yaml`. Declaring `data` again without `name:` conflicts with `infra/compose.yaml` on `main` (`networks.data conflicts with imported resource`) | docs (header comment: run with `-f infra/compose.yaml -f api/compose.yaml`; checked with `docker compose config` against `infra/compose.yaml` on `main` and on `chore/infra-compose`) |
| 7 | compose, this change | a failed migration logs the JSON error line `migration failed: OperationalError`, then an uncaught traceback (no password in either) | wont-fix (archived follow-up 30) |
| 8 | iw-reviewer, whole range | a URL whose password contains whitespace is not redacted (`\S*` stops at the space; same before this change) | docs (`api/README.md`: no whitespace in a hand-set password; generated passwords are hex) |
| 9 | iw-reviewer, whole range | `0003` upgrade fails if a row already has `text = ''` | docs (revision docstring; nothing is deployed and the scraper never stores empty text) |
| 10 | iw-reviewer, declined | `JsonFormatter` writes the `_EXTRA_KEYS` values (`path`, `reason`, ...) without `redact()` | new-item (change `api-v1`, once it logs request paths or query strings) |
| 11 | iw-reviewer, declined | `DATABASE_ADMIN_URL` is visible through `docker inspect` on `api-migrate` | wont-fix (config is env-only by convention; Docker secrets after the hackathon if wanted) |
