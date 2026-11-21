# Design

## Context

Three services share one Postgres 17 database ([ADR 0202](../../../.docs/decisions/0202-deployment-topology.md)): the scraper writes `sources` (run status), `documents` and `job_errors`; analytics writes `findings` and `calibration_points`; the API reads everything and writes finding status, notes and `sources`. [ADR 0303](../../../.docs/decisions/0303-database-schema-ownership.md) puts all migrations in Alembic under `api/`. `infra/` already runs Postgres on the internal `iw-data` network with two roles: `iw_admin` (DDL) and `iw_app` (CRUD only). `infra/postgres/init/01-app-role.sh` sets default privileges so tables created by `iw_admin` are CRUD-able by `iw_app`. Integration #1 (Sat 17:00) needs `documents` and `findings`; Redis and MinIO arrive in the parallel `infra-compose` change. See `proposal.md` for scope.

## Goals / Non-Goals

**Goals:**
- A migrated schema in one `alembic upgrade head`, before any writer starts.
- Constraints in the database for the rules other teams rely on: dedup of documents, one finding per `(document_id, module)`, contract enums.
- A package skeleton (`api/src/investwatch_api/`) that change `api-v1` builds the REST service on, with no route code yet.

**Non-Goals:**
- REST, Socket.IO, Redis, MinIO (change `api-v1`).
- `registry_firms`, `gold_labels` (later revisions, added by the analytics changes that need them).
- Writer code in the scraper or analytics; this change only documents the SQL they use.

## Decisions

1. **Driver: psycopg 3 for both Alembic and the API (SQLAlchemy 2, `postgresql+psycopg://`).** One driver serves Alembic's sync migrations and the API's async engine. Alternatives: asyncpg for the API plus psycopg for Alembic (two drivers, two URL schemes, asyncpg needs a separate sync driver for Alembic anyway); SQLAlchemy Core with no ORM (kept: tables are declared as Core `Table` objects, no ORM classes, because the API mostly runs filtered selects and analytics does its own inserts). Recorded in ADR 0307.
2. **Columns plus JSONB.** Fields that are filtered, sorted, joined or constrained are columns; nested contract objects are JSONB. `documents.payload` holds `author, links, media, screenshots, blocks, scrape_meta`; `findings` has JSONB `firm, advertiser, rules, model`. Alternatives: one JSONB blob per row (no constraints, slow filters) or fully normalised `rules`/`blocks` tables (many joins and inserts for data that is only ever read whole). Recorded in ADR 0307.
3. **Enums as `text` + CHECK, not Postgres ENUM types.** Values come from `contracts/schemas/`. Adding a value later is one `ALTER TABLE ... DROP/ADD CONSTRAINT` in a revision, while `ALTER TYPE ... ADD VALUE` cannot run inside a transaction in every case and cannot remove a value. `target_modules` is `text[]` with a CHECK that it is non-empty and a subset of `{M1,M2,M3}`.
4. **Document dedup index: `UNIQUE (source_id, content_hash) NULLS NOT DISTINCT WHERE content_hash IS NOT NULL`.** `NULLS NOT DISTINCT` (Postgres 15+) makes ad-hoc documents (`source_id` null) deduplicate too; the partial predicate stops rows without a hash from colliding. The scraper inserts with `INSERT ... ON CONFLICT (source_id, content_hash) WHERE content_hash IS NOT NULL DO NOTHING`: the untargeted form also works with this index but would silently drop a document whose `id` collides, so the README gives the targeted form (review of group 2). The scraper's own spec (`scraper-v1`, document-ingest) keeps its pre-upload lookup.
5. **Published marker: `documents.stream_published_at timestamptz NULL`** plus a partial index `ON documents (created_at) WHERE stream_published_at IS NULL`. Named so it cannot be confused with the contract field `published_at` (content publication date). The sweep is `SELECT id FROM documents WHERE stream_published_at IS NULL AND created_at < now() - interval '1 minute' ORDER BY created_at, id LIMIT n`; the grace keeps it from re-announcing a row an ingest has just committed. Alternative: an outbox table; rejected for v1, as `scraper-v1` design already says. This answers that design's open question (column, not table).
6. **Findings upsert key `UNIQUE (document_id, module)`.** The documented statement for analytics is `INSERT ... ON CONFLICT (document_id, module) DO UPDATE SET score, title, summary, firm, advertiser, rules, content_excerpt, model, updated_at = excluded.*`; it leaves `id`, `detected_at`, `status` and `note` alone so an analyst's work survives a re-scan. A changed page is a new `documents` row (new `content_hash`), so it gets a new finding; that is intended. Whether a re-scan with a much higher score should reopen a closed finding is a product rule, listed under Open Questions.
7. **Denormalised `url` and `platform` on findings** as in the `Finding` contract; `source_id` is not copied, the API joins `documents` for that filter.
8. **Timestamps `timestamptz`, ids `uuid` without a server default.** Producers generate UUID v4 ids (integration-plan §7). `created_at`/`updated_at` on `sources` and `created_at` on `documents` default to `now()`.
9. **Settings from env only:** `DATABASE_ADMIN_URL` for migrations, `DATABASE_URL` (as `iw_app`) for the service. `api/compose.yaml` builds both from the `POSTGRES_*` variables already in `.env.example`, so no new secret is introduced. The Alembic `env.py` refuses to run if `DATABASE_ADMIN_URL` is unset instead of falling back to `DATABASE_URL`.
10. **Tests against a real Postgres.** Constraint behaviour (`NULLS NOT DISTINCT`, partial indexes, role grants) is what matters, so the tests run against Postgres 17 from `infra/compose.yaml` (or a disposable container with the same init script) and are skipped, not failed, when `TEST_DATABASE_ADMIN_URL` is unset. SQLite is not a substitute.

## Risks / Trade-offs

- [Scraper or analytics start before migrations] → `api-migrate` one-shot service, writers use `depends_on: condition: service_completed_successfully`; the root `include:` line is added with `infra-compose`.
- [`iw_app` also gets CRUD on `alembic_version`] → the initial revision revokes `iw_app` privileges on `alembic_version`.
- [A teammate needs a new column after Integration #1] → each change is a new revision in `api/migrations/versions/`, reviewed by Damian; never an edit of an applied revision.
- [Analytics `schema.sql` drift] → `.docs/analytics-plan.md` §12.4 allowed a temporary `analytics/sql/schema.sql`; once this lands, analytics uses these tables and no such file is created.
- [JSONB fields not validated by the database] → producers validate against `contracts/` before insert (contracts `CLAUDE.md`); the round-trip test checks the mocks.

## Migration Plan

Fresh databases only (nothing is deployed). Order: Postgres healthy → `api-migrate` (`alembic upgrade head` as `iw_admin`) → scraper, analytics, api. Rollback: `alembic downgrade base` locally, or `docker compose down -v` (also re-runs the role init script).

## Open Questions

- Does a re-scan that raises the score of a `closed` or `false_positive` finding reopen it (status back to `new`)? Default in this design: no, status is never changed by analytics.
- `calibration_points` is written by analytics eval (`.docs/analytics-plan.md` §8). Does `GET /calibration` show only the gold-set run from this table, or combine it with live analyst labels (integration-plan §5)? Affects change `api-v1` only, not this schema.
- `registry_firms` and `gold_labels`: confirm they come as later revisions with the analytics changes, not in this one.
