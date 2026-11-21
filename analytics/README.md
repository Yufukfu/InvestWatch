# analytics

Analytics service: preprocessing, KNF firm registry, UKNF rule engine, modules M1–M3, LLM integration.

- **Owner:** Damian
- **Status:** pipeline (changes `analytics-skeleton`, `analytics-m1-m3`): M2 (rules-only R1–R3) for a registered firm's own material, M1 (signals S1.1–S1.7) for third-party ads of a registered firm, M3 (signals S3.1–S3.8) for offers that may indicate investment advice by an entity outside the registry. Service (change `analytics-worker`): a worker consumes the Redis Stream `iw:documents`, upserts `findings` in Postgres and publishes `finding.created` / `finding.high_risk` on `iw:events`. No LLM yet (`model.llm = null`): S1.5 is always `uncertain`, and S3.3/S3.4 are `uncertain` when the rules find a candidate phrase, `pass` otherwise, until it lands.
- **Registry:** the default registry is `registry/knf.csv`, the real KNF register of investment firms (749 firms, snapshot of 2026-11-21; change `analytics-knf-registry`). At start-up the worker logs `registry_loaded` with the snapshot date. R1 passes only on a firm's official name; a former or trade name alone makes it `uncertain`. `registry/seed.csv` (4 fictional firms) is the test fixture: it logs a `registry_seed` WARNING if used, and M3 findings then add "(dane demonstracyjne)" (`Registry.demo`: no firm has a `source_url`). Files, source and refresh: [`registry/README.md`](registry/README.md).
- **Privacy:** rule `evidence` and `advertiser` copy scraped author names, handles, profile and referral links verbatim (cut to 200-300 characters) into `findings`, and the `iw:events` messages carry the title, which names the advertiser, so treat them as personal data taken from public posts.
- **Evaluation:** gold-set evaluation (change `analytics-eval-calibration`): `eval/gold.jsonl`, `python eval/run.py`, and the one-shot `analytics-eval` service that feeds the calibration panel (section "Gold-set evaluation" below).

## Modules and routing

A document gives at most one finding per module ([`modules/router.py`](src/investwatch_analytics/modules/router.py), [`pipeline.py`](src/investwatch_analytics/pipeline.py)):

| Who publishes | Registry | Module |
|---|---|---|
| a registered firm (the page host or the author's profile host is its domain; any platform; a handle alone is not enough) | — | M2 for that firm |
| a foreign firm without a Polish branch (`foreign_no_branch`), its own material | — | nothing (`out_of_scope_m2_foreign_no_branch`): M2 is for firms registered in Poland, including Polish branches |
| `firm_own` source | firm named or page on a firm domain | M2 |
| `firm_own` source | no firm | M3 if advisory signals, else nothing (`no_signals`) |
| a third party | firm named in the text or linked | M1 (a foreign firm without a Polish branch only if the ad targets Poland, else `not_targeting_poland`), plus M3 against the publisher when the advice offer is the publisher's own |
| a third party | no firm | M3 if advisory signals, else nothing (`no_signals`) |

Before routing to a module, the topic gate drops a `third_party` or `unknown` document that has no investment signal: no term of [`gate_terms.yaml`](src/investwatch_analytics/gate_terms.yaml) and no registry firm. The drop is logged as `off_topic` with `dict_hits`, never with text, and counted in Redis `iw:stats:gate` (`passed`, `dropped`, `bypassed`). `firm_own` documents are never gated. A near-duplicate (MinHash Jaccard ≥ 0.8 over word 5-shingles) is analyzed as usual. Its summary names the original's URL, and it fires no second `finding.high_risk` for its group and module ([ADR 0314](../.docs/decisions/0314-topic-gate-and-near-duplicates.md)).

M1 score: σ(bias + Σ w·x), how certain this is a third-party ad of the firm. M3 score: the same form, capped at 0.4 unless S3.4 (a recommendation to buy, sell or hold financial instruments) is found; M3 means "may indicate" investment advice, and the summary says when personalisation (art. 76) is unconfirmed ([ADR 0308](../.docs/decisions/0308-m3-s34-gate.md)). Signals, weights and dictionaries: [`rules/m1_signals.yaml`](src/investwatch_analytics/rules/m1_signals.yaml), [`rules/m3_signals.yaml`](src/investwatch_analytics/rules/m3_signals.yaml). Evidence may quote the author handle, a link or the page URL as well as the text. Routing and the M1/M3 rules read at most the first 200 000 characters (`SCAN_MAX` in `pipeline.py`); firm names are compared after NFKC and removal of zero-width characters, with quotes cut from the original text. Specs: [`m1-third-party-signals`](../openspec/specs/m1-third-party-signals/spec.md), [`m3-unauthorized-advice-signals`](../openspec/specs/m3-unauthorized-advice-signals/spec.md).

## Run the worker (compose)

The `analytics` service in [`compose.yaml`](compose.yaml) joins the root stack (`docker compose up --build` from the repository root). It needs `postgres`, `redis` (infra) and the one-shot `api-migrate` (api), and builds `DATABASE_URL` (app role `iw_app`) and `REDIS_URL` from the root `.env` (`scripts/init-env.sh`). Feed it a document by hand:

```bash
# after inserting a documents row (the scraper does this, then XADDs)
docker compose exec redis sh -c 'REDISCLI_AUTH="$REDIS_PASSWORD" redis-cli XADD iw:documents "*" document_id <uuid> schema v1'
```

Per message the worker loads the row, runs the pipeline, saves all findings in one transaction, publishes the events and only then acknowledges (XACK). A redelivery or a second message for the same document updates the finding (`(document_id, module)`) and publishes nothing. A malformed message, a missing row or an invalid document is logged and acknowledged; an unexpected error is retried up to `MAX_DELIVERIES`; a Postgres or Redis outage is retried with backoff and never acknowledged. `GET /health` on port 8001 (inside the stack only) answers 200 or 503 with `redis` / `db` flags. Specs: [`document-stream-worker`](../openspec/specs/document-stream-worker/spec.md), [`finding-storage`](../openspec/specs/finding-storage/spec.md), [`finding-events`](../openspec/specs/finding-events/spec.md); design and review follow-ups: [`openspec/changes/archive/2026-11-21-analytics-worker/`](../openspec/changes/archive/2026-11-21-analytics-worker/design.md).

## Gold-set evaluation (calibration panel)

[`eval/gold.jsonl`](eval/gold.jsonl) holds 69 labeled documents: 35 for M2 (every ZASÓB rule R1-R18 with a violating and a compliant example), 18 for M1 and 18 for M3, about a third of them hard cases. No official sample set was available (`doc/` has the criteria only), so 67 lines are synthetic and 2 are built around phrasings ZASÓB quotes (`origin: zasob-example`); all use fictional firms. The labeling rules are in [`eval/README.md`](eval/README.md).

```bash
.venv/Scripts/python eval/run.py              # JSON report on stdout, rules-only, no database
.venv/Scripts/python eval/run.py --db         # also store the run in calibration_points (DATABASE_URL)
docker compose run --rm analytics-eval        # the same in the stack
```

The one-shot `analytics-eval` service runs `--db` on every `docker compose up`, after `api-migrate`. It stores a module's run only when the gold set, the pipeline version or the results changed, so restarts add nothing. `GET /api/calibration` adds analysts' `confirmed` / `false_positive` labels to that run's counts. The report gives precision, recall and F1 per module on the thresholds 0.05-0.95, counted the same way as the API. Per rule or signal it gives two readings: **`strict` (the headline: `uncertain` counts as not flagged)** and `review` (`uncertain` counts as flagged). Exit codes: 0 ok; 1 a labeled module produced no finding (`not_run`, no rows stored for it) or a gold document crashed the pipeline (nothing stored); 2 invalid gold set or configuration; 3 the database write failed.

Latest rules-only numbers (build `main` bb770a0 with this change). Recommended threshold = higher end of the plateau of thresholds whose F1 is within 0.02 of the best; rules as `strict` precision / recall:

| Module (gold cases) | Recommended (plateau) | At it | At the old ADR 0305 default | Rules |
|---|---|---|---|---|
| M1 (18: 10 / 8) | 0.65 (0.40-0.65) | precision 1.0, recall 0.8, F1 0.889 | 0.6: F1 0.889 | S1.1 1.0 / 0.94, S1.2 1.0 / 0.56, S1.6 1.0 / 1.0, S1.7 1.0 / 0.9 |
| M2 (35: 23 / 12) | 0.1 (0.05-0.1) | precision 0.933, recall 0.609, F1 0.737 | 0.5: F1 0.414 | R1 1.0 / 1.0, R2 1.0 / 0.67, R3 0.78 / 1.0, R4 1.0 / 0.5, R6 1.0 / 1.0, R14 1.0 / 1.0, R17 1.0 / 0.33, R18 1.0 / 1.0 (with `analytics-llm-p0`; R5, R7-R13, R15, R16 not built) |
| M3 (18: 10 / 8) | 0.25 (0.25 only); **default 0.4** (gate cap) | at 0.25: precision 0.875, recall 0.7, F1 0.778; at 0.4: precision 1.0, recall 0.4, F1 0.571 | 0.7: F1 0 | S3.1 1.0 / 0.67, S3.2 1.0 / 0.71, S3.8 1.0 / 1.0 |

M3's default is raised to the S3.4 gate cap (0.4, ADR 0308) so capped findings never alert by default; it is re-evaluated once the LLM scores S3.4 (ADR 0316). S1.5, S3.3 and S3.4 need the LLM (`uncertain` rules-only, `strict` recall 0).

**Default thresholds** ([ADR 0316](../.docs/decisions/0316-default-thresholds-from-evaluation.md)): the recommended thresholds, M3 raised to its gate cap, are the defaults the API writes when `iw:settings:thresholds` is missing (M1 0.65, M2 0.1, M3 0.4; M2 re-measured from 0.25 with the P0 rules of `analytics-llm-p0`, [ADR 0317](../.docs/decisions/0317-hosted-llm-gemma-on-gemini-api.md)). [`eval/thresholds.json`](eval/thresholds.json) is the source. `python eval/run.py --write-thresholds` rewrites it, and the API's `DEFAULTS` and `events.DEFAULT_THRESHOLDS` must be copied from it: `tests/test_eval_thresholds.py` fails until they match a fresh run. M2's value is low because only part of the 18 rules run today, and it moves when more rules or the LLM land.

## Run locally (no infrastructure)

Python 3.12+.

```bash
cd analytics
python -m venv .venv && .venv/Scripts/python -m pip install -r requirements-dev.txt -e .   # Linux/macOS: .venv/bin/python
REGISTRY_CSV=registry/seed.csv .venv/Scripts/python -m investwatch_analytics.cli ../contracts/mocks/documents.json > findings.json
.venv/Scripts/python ../contracts/validate.py finding findings.json
```

The mocks name the fictional seed firms, so this run sets `REGISTRY_CSV` to the seed; with the default (the real KNF register) their firms are unmatched and R1 fails.

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

The Postgres tests apply [`tests/sql/schema.sql`](tests/sql/schema.sql), a hand-copied, test-only mirror of the `api/` migrations 0001-0003 (verified identical with `pg_dump --schema-only`; an automated drift check is a follow-up). CI sets `TEST_DATABASE_ADMIN_URL` and `IW_TEST_REDIS_URL`, so these tests run there too.

## Configuration (env)

| Variable | Default | Meaning |
|---|---|---|
| `REGISTRY_CSV` | `registry/knf.csv` (the real KNF register snapshot; found from a source checkout, `pip install -e` or the image, which keeps `registry/` next to `src/`) | firm registry, files and refresh in [`registry/README.md`](registry/README.md) |
| `LOG_LEVEL` | `INFO` | log level |
| `DATABASE_URL` | worker: required | Postgres, app role (`postgresql://iw_app:...@postgres:5432/investwatch`) |
| `REDIS_URL` | worker: required | Redis (`redis://:<password>@redis:6379/0`) |
| `WORKER_CONSUMER` | hostname | consumer name in the group `analytics` |
| `STREAM_BLOCK_MS` | `5000` | XREADGROUP block time |
| `CLAIM_MIN_IDLE_MS` | `60000` | XAUTOCLAIM: reclaim a message idle this long (a consumer died) |
| `MAX_DELIVERIES` | `5` | unexpected errors on one message before it is acknowledged as `max_deliveries_exceeded` |
| `HEALTH_PORT` | `8001` | `/health` |
| `MAX_DOCUMENT_BYTES` | `2000000` | a bigger document (`text` + `payload`) is acknowledged as `invalid_document` instead of risking an out-of-memory kill |
| `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY` | empty | the LLM client (ADR 0304, 0317); empty = rules-only. Limits in [`.env.example`](.env.example) |
| `EMBED_BASE_URL` | empty (off) | OpenAI-compatible embeddings endpoint, local only: `http://ollama:11434/v1` with `docker compose --profile llm up` ([ADR 0313](../.docs/decisions/0313-embeddings-model-and-serving.md)). Off = `model.embedder = null` |
| `EMBED_MODEL`, `EMBED_DIM` | `bge-m3`, `1024` | model and vector size; a vector of another size is rejected (`embed_malformed`). Pull it with `ollama-pull` (issue #65) or by hand: `docker compose exec ollama ollama pull bge-m3` |
| `EMBED_TIMEOUT_S`, `EMBED_MAX_CHARS`, `EMBED_CACHE_TTL_S`, `EMBED_BREAKER_FAILURES`, `EMBED_BREAKER_COOLDOWN_S` | `5`, `4000`, `604800`, `3`, `60` | per call, input cut, vector cache `iw:emb:v1:*` TTL, circuit breaker. `LLM_DOC_BUDGET_S + 3 + EMBED_TIMEOUT_S` must stay below `CLAIM_MIN_IDLE_MS` |
| `GATE_ENABLED`, `GATE_SIM_THRESHOLD` | `true`, `0.45` | topic gate on/off; the threshold is for the (not built) similarity rescue |
| `NEARDUP_NUM_PERM`, `NEARDUP_BANDS`, `NEARDUP_THRESHOLD`, `NEARDUP_MAX_CHARS`, `NEARDUP_TTL_S` | `128`, `32`, `0.8`, `50000`, `2592000` | MinHash near-dup index `iw:neardup:v1:*` in Redis (worker only; the CLI has none) |
| `CONTRACTS_DIR`, `TEST_DATABASE_URL` (or CI's `TEST_DATABASE_ADMIN_URL`), `TEST_REDIS_URL` (or CI's `IW_TEST_REDIS_URL`) | unset | tests only |

## Where things are

- `src/investwatch_analytics/pipeline.py`: `analyze_document(doc, *, registry, catalogue, now, signals, judge, gate, embedder, neardup)` → `Analysis` (findings, gate decision, near-dup group, embedding); `analyze(...)` → its findings. Pure apart from the injected judge, embedder and near-dup index, all off by default.
- `src/investwatch_analytics/gate.py`, `gate_terms.yaml`: the topic gate; `embeddings/`: client, cache, breaker, never-raising embedder; `neardup.py`: MinHash and the Redis LSH index.
- `src/investwatch_analytics/rules/m2_rules.yaml`: all 18 UKNF rules (name, severity, legal basis, dictionaries). Only entries with `implemented: true` run.
- `src/investwatch_analytics/rules/m2.py`: R1 firm identification, R2 ad labeling, R3 risk information next to return claims.
- `src/investwatch_analytics/rules/m1.py`, `rules/m3.py`: the M1/M3 signal classes; `modules/m1.py`, `modules/m3.py`: the M1/M3 findings; `modules/advertiser.py`: publisher identity and `advertiser`; `rules/scoring.py`: the sigmoid score.
- `src/investwatch_analytics/worker.py`: the stream consumer (`python -m investwatch_analytics.worker`); `storage.py`: the store interface and the Postgres store; `events.py`: `iw:events` publisher and the live threshold read (ADR 0305); `health.py`: `/health`; `testing.py`: test doubles (`InMemoryStore`, `NoopPublisher`), never imported by the worker.
- `src/investwatch_analytics/evaluation/`: gold-set loader and validation (`gold.py`, `known_ids.py`), metrics with the API's counting (`metrics.py`), runner (`runner.py`), `calibration_points` writer (`store.py`), command line (`__main__.py`); `eval/`: the gold set, its fictional registry and `run.py`.
- Spec: [`openspec/specs/document-analysis/`](../openspec/specs/document-analysis/spec.md) and [`openspec/specs/m2-compliance-rules/`](../openspec/specs/m2-compliance-rules/spec.md); design and review follow-ups: [`openspec/changes/archive/2026-11-21-analytics-skeleton/`](../openspec/changes/archive/2026-11-21-analytics-skeleton/); plan: [`.docs/analytics-plan.md`](../.docs/analytics-plan.md).
