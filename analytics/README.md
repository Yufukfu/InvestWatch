# analytics

Analytics service: preprocessing, KNF firm registry, UKNF rule engine, modules M1–M3, LLM integration.

- **Owner:** Damian
- **Status:** pipeline (changes `analytics-skeleton`, `analytics-m1-m3`): M2 (rules-only R1–R3) for a registered firm's own material, M1 (signals S1.1–S1.7) for third-party ads of a registered firm, M3 (signals S3.1–S3.8) for offers that may indicate investment advice by an entity outside the registry. Service (change `analytics-worker`): a worker consumes the Redis Stream `iw:documents`, upserts `findings` in Postgres and publishes `finding.created` / `finding.high_risk` on `iw:events`. No LLM yet (`model.llm = null`); semantic signals (S1.5, S3.3, S3.4) stay `uncertain` until it lands.
- **Registry:** [`registry/seed.csv`](registry/seed.csv) holds three fictional firms until the real KNF loader lands, so M1/M2 only recognise those firms and every other entity is treated as outside the registry.

## Modules and routing

A document gives at most one finding per module ([`modules/router.py`](src/investwatch_analytics/modules/router.py), [`pipeline.py`](src/investwatch_analytics/pipeline.py)):

| Who publishes | Registry | Module |
|---|---|---|
| a registered firm (its domain, its profile host or its handle; any platform) | — | M2 for that firm |
| `firm_own` source | firm named or page on a firm domain | M2 |
| `firm_own` source | no firm | M3 if advisory signals, else nothing (`no_signals`) |
| a third party | firm named in the text or linked | M1 (a foreign firm only if the ad targets Poland, else `not_targeting_poland`), plus M3 against the publisher when the advice offer is the publisher's own |
| a third party | no firm | M3 if advisory signals, else nothing (`no_signals`) |

M1 score: σ(bias + Σ w·x), how certain this is a third-party ad of the firm. M3 score: the same form, capped at 0.4 unless S3.4 (a recommendation to buy, sell or hold financial instruments) is found. Signals, weights and dictionaries: [`rules/m1_signals.yaml`](src/investwatch_analytics/rules/m1_signals.yaml), [`rules/m3_signals.yaml`](src/investwatch_analytics/rules/m3_signals.yaml). Evidence may quote the author handle, a link or the page URL as well as the text. Specs: [`m1-third-party-signals`](../openspec/specs/m1-third-party-signals/spec.md), [`m3-unauthorized-advice-signals`](../openspec/specs/m3-unauthorized-advice-signals/spec.md).

## Run the worker (compose)

The `analytics` service in [`compose.yaml`](compose.yaml) joins the root stack (`docker compose up --build` from the repository root). It needs `postgres`, `redis` (infra) and the one-shot `api-migrate` (api), and builds `DATABASE_URL` (app role `iw_app`) and `REDIS_URL` from the root `.env` (`scripts/init-env.sh`). Feed it a document by hand:

```bash
# after inserting a documents row (the scraper does this, then XADDs)
docker compose exec redis sh -c 'REDISCLI_AUTH="$REDIS_PASSWORD" redis-cli XADD iw:documents "*" document_id <uuid> schema v1'
```

Per message the worker loads the row, runs the pipeline, saves all findings in one transaction, publishes the events and only then acknowledges (XACK). A redelivery or a second message for the same document updates the finding (`(document_id, module)`) and publishes nothing. A malformed message, a missing row or an invalid document is logged and acknowledged; an unexpected error is retried up to `MAX_DELIVERIES`; a Postgres or Redis outage is retried with backoff and never acknowledged. `GET /health` on port 8001 (inside the stack only) answers 200 or 503 with `redis` / `db` flags. Specs: [`document-stream-worker`](../openspec/specs/document-stream-worker/spec.md), [`finding-storage`](../openspec/specs/finding-storage/spec.md), [`finding-events`](../openspec/specs/finding-events/spec.md); design and review follow-ups: [`openspec/changes/archive/2026-11-21-analytics-worker/`](../openspec/changes/archive/2026-11-21-analytics-worker/design.md).

## Run locally (no infrastructure)

Python 3.12+.

```bash
cd analytics
python -m venv .venv && .venv/Scripts/python -m pip install -r requirements-dev.txt -e .   # Linux/macOS: .venv/bin/python
.venv/Scripts/python -m investwatch_analytics.cli ../contracts/mocks/documents.json > findings.json
.venv/Scripts/python ../contracts/validate.py finding findings.json
```

The CLI reads one `ScrapedDocument` or a list of them and writes `Finding`s as a JSON list to stdout. JSON logs go to stderr. An invalid document, or one whose analysis fails, is logged and skipped. Exit codes: 0 ok; 1 at least one document failed analysis (the others' findings are still written); 2 bad input, bad configuration, or no valid document (nothing on stdout).

## Tests

```bash
CONTRACTS_DIR=../contracts .venv/Scripts/python -m pytest -q
```

Without `CONTRACTS_DIR`, the contract tests are skipped, not failed. The Postgres store and real-Redis tests need throwaway servers on loopback (they are skipped without them):

```bash
docker run -d --rm --name iw-test-analytics-pg -e POSTGRES_PASSWORD=test -p 127.0.0.1:55433:5432 public.ecr.aws/docker/library/postgres:17-alpine
docker run -d --rm --name iw-test-analytics-redis -p 127.0.0.1:56380:6379 public.ecr.aws/docker/library/redis:7-alpine
TEST_DATABASE_URL=postgresql://postgres:test@127.0.0.1:55433/postgres TEST_REDIS_URL=redis://127.0.0.1:56380/0 CONTRACTS_DIR=../contracts .venv/Scripts/python -m pytest -q
```

The Postgres tests apply [`tests/sql/schema.sql`](tests/sql/schema.sql), a test-only mirror of the `api/` migrations.

## Configuration (env)

| Variable | Default | Meaning |
|---|---|---|
| `REGISTRY_CSV` | `registry/seed.csv` (fictional firms; found from a source checkout, `pip install -e` or the image, which keeps `registry/` next to `src/`) | KNF firm registry, format in [`registry/README.md`](registry/README.md) |
| `LOG_LEVEL` | `INFO` | log level |
| `DATABASE_URL` | worker: required | Postgres, app role (`postgresql://iw_app:...@postgres:5432/investwatch`) |
| `REDIS_URL` | worker: required | Redis (`redis://:<password>@redis:6379/0`) |
| `WORKER_CONSUMER` | hostname | consumer name in the group `analytics` |
| `STREAM_BLOCK_MS` | `5000` | XREADGROUP block time |
| `CLAIM_MIN_IDLE_MS` | `60000` | XAUTOCLAIM: reclaim a message idle this long (a consumer died) |
| `MAX_DELIVERIES` | `5` | unexpected errors on one message before it is acknowledged as `max_deliveries_exceeded` |
| `HEALTH_PORT` | `8001` | `/health` |
| `MAX_DOCUMENT_BYTES` | `2000000` | a bigger document (`text` + `payload`) is acknowledged as `invalid_document` instead of risking an out-of-memory kill |
| `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY` | empty | reserved for the LLM client (ADR 0304); unused, rules-only |
| `CONTRACTS_DIR`, `TEST_DATABASE_URL`, `TEST_REDIS_URL` | unset | tests only |

## Where things are

- `src/investwatch_analytics/pipeline.py`: `analyze(doc, *, registry, catalogue, now)` → findings. Pure, no I/O.
- `src/investwatch_analytics/rules/m2_rules.yaml`: all 18 UKNF rules (name, severity, legal basis, dictionaries). Only entries with `implemented: true` run.
- `src/investwatch_analytics/rules/m2.py`: R1 firm identification, R2 ad labeling, R3 risk information next to return claims.
- `src/investwatch_analytics/rules/m1.py`, `rules/m3.py`: the M1/M3 signal classes; `modules/m1.py`, `modules/m3.py`: the M1/M3 findings; `modules/advertiser.py`: publisher identity and `advertiser`; `rules/scoring.py`: the sigmoid score.
- `src/investwatch_analytics/worker.py`: the stream consumer (`python -m investwatch_analytics.worker`); `storage.py`: Postgres and in-memory stores; `events.py`: `iw:events` publisher and the live threshold read (ADR 0305); `health.py`: `/health`.
- Spec: [`openspec/specs/document-analysis/`](../openspec/specs/document-analysis/spec.md) and [`openspec/specs/m2-compliance-rules/`](../openspec/specs/m2-compliance-rules/spec.md); design and review follow-ups: [`openspec/changes/archive/2026-11-21-analytics-skeleton/`](../openspec/changes/archive/2026-11-21-analytics-skeleton/); plan: [`.docs/analytics-plan.md`](../.docs/analytics-plan.md).
