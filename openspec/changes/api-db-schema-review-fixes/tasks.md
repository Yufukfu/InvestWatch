## 1. Null JSONB fields

- [x] 1.1 Test: a finding inserted with `firm`, `advertiser`, `model` = `None` has `firm IS NULL` (and the other two) in SQL
- [x] 1.2 `JSONB(none_as_null=True)` on the three nullable columns; `alembic check` stays clean
- [x] 1.3 Mutation check — mutations: 3 tried, 3 caught

## 2. Redaction

- [x] 2.1 Test: `postgresql://iw_admin:p@ss@word@postgres:5432/db` leaves no part of the password in the whole message
- [x] 2.2 `_URL_CREDENTIALS` matches up to the last `@` of the token
- [x] 2.3 Mutation check — mutations: 3 tried, 3 caught

## 3. Tests that can fail

- [x] 3.1 EXPLAIN the compiled `unpublished_documents()` and findings list statements instead of hand-typed SQL
- [x] 3.2 Mock round-trip keeps explicit nulls for nullable fields
- [x] 3.3 One test compares the contract enums in `contracts/schemas/*.json` with the CHECK definitions in `pg_constraint`; drop or rename the tests that compare `tables.py` with itself; fix the `alembic check` docstring
- [x] 3.4 Mutation check — mutations: 10 tried, 10 caught (the round-trip mutant first survived because the test edit had not applied; caught after the fix)

## 4. Non-empty document text

- [x] 4.1 Test: inserting a document with `text = ''` fails with a check violation
- [x] 4.2 Revision `0003` adds `ck_documents_text_not_empty`, with downgrade; `tables.py` matches
- [x] 4.3 Mutation check — mutations: 4 tried, 4 caught

## 5. Compose

- [x] 5.1 Root `compose.yaml` includes `api/compose.yaml`; `api/compose.yaml` does not redeclare the data network and depends on `infra/compose.yaml`'s `postgres`
- [x] 5.2 Hand-run `docker compose up` on an empty volume with a throwaway project name: `api-migrate` exits 0 (output kept for the PR body)
- [x] 5.3 Mutation check — mutations: n/a, config-only group (compose values, no logic); verified by `docker compose config` against `infra/compose.yaml` on `main` and on `chore/infra-compose`, and by the hand-run `up`

## 6. Closing

- [ ] 6.1 Apply iw-docs-update (STATUS row, duplicate AI log row, README, follow-ups) and add the iw-ai-log row
- [ ] 6.2 Run iw-pr-review checks and fix real findings
