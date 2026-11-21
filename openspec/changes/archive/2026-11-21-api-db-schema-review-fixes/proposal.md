## Why

Kacper's review of PR #15 (`api-db-schema`, at 73680fa) asked for changes. Three findings block approval: nullable JSONB contract fields are stored as JSON `null` instead of SQL `NULL`, `.docs/STATUS.md` is stale, and `.docs/ai-workflow.md` has a duplicate row. The migration step is not part of the root stack and `api/compose.yaml` cannot be included next to `infra/compose.yaml`. The log redactor leaks part of a password containing `@`. Several tests cannot fail from a production change. Fixing these before merge keeps `IS NULL` filters in `api-v1` correct and makes `docker compose up` create the schema for Integration #1.

## What Changes

- `findings.firm`, `advertiser` and `model` store a contract `null` as SQL `NULL` (`JSONB(none_as_null=True)`, no new revision: the column type is unchanged).
- Revision `0003` adds `CHECK (text <> '')` on `documents.text` (closes archived follow-up 28 as a second line of defence).
- Root `compose.yaml` includes `api/compose.yaml`. `api/compose.yaml` no longer redeclares the data network, and joins `infra/compose.yaml`'s `postgres` the way `web/compose.yaml` joins the gateway's network.
- `redact()` masks the userinfo up to the last `@` of a URL token.
- Tests: `firm IS NULL` after a `None` insert; EXPLAIN on the statements from `sql.py`; the mock round-trip keeps explicit nulls; one test compares the contract enums in `contracts/schemas/*.json` with the CHECK definitions in `pg_constraint`; tests that only compared `tables.py` with itself are dropped or renamed.
- Docs: Damian's `.docs/STATUS.md` row, the duplicate `.docs/ai-workflow.md` row removed, `api/README.md` compose note, follow-ups for review items 7, 12 and 13.

## Capabilities

### New Capabilities
- none

### Modified Capabilities
- `database-schema`: migration step is part of the root stack; null JSONB fields are SQL `NULL`; round-trip keeps explicit nulls; enum CHECKs match the contracts; document text is non-empty.

## Impact

- Owner: C (`api/`). One new revision (`0003`); `0001` and `0002` are not edited. No contract, REST route or event changes.
- Root `compose.yaml` gets one `include:` line (owner B's file, requested in his review).
- Out of scope: review items 7 (sweep locking), 12 (`finding_status_history`, for `api-v1`) and 13 (no CI) are recorded in this change's `follow-ups.md`. `openspec/changes/api-v1/` stays in PR #15 as a proposal only (review item 14).
