# analytics

Analytics service: preprocessing, KNF firm registry, UKNF rule engine, modules M1–M3, LLM integration.

- **Owners:** [`.github/CODEOWNERS`](../.github/CODEOWNERS)
- **Status:** pipeline (changes `analytics-skeleton`, `analytics-m1-m3`): M2 (R1–R8, R11, R12a, R12b, R13–R18; R11, R12a, R12b, R15 and R16 from change `analytics-m2-p1-rules`, the visual R5, R7, R8 and R13 from change `analytics-m2-visual-rules`) for a registered firm's own material, M1 (signals S1.1–S1.7) for third-party ads of a registered firm, M3 (signals S3.1–S3.8) for offers that may indicate investment advice by an entity outside the registry. Service (change `analytics-worker`): a worker consumes the Redis Stream `iw:documents`, upserts `findings` in Postgres and publishes `finding.created` / `finding.high_risk` on `iw:events`. LLM layer (change `analytics-llm-p0`): checks the rules defer go to an OpenAI-compatible model, hosted Gemma 4 by default, local Gemma through Ollama as the swap (section "LLM: hosted Gemma or local Ollama" below). Without a reachable model every finding is rules-only (`model.llm = null`, the summary ends with "Tryb regułowy (bez modelu językowego).").
- **Registry:** the default registry is `registry/knf.csv`, the real KNF register of investment firms (749 firms, snapshot of 2026-11-21; change `analytics-knf-registry`). At start-up the worker logs `registry_loaded` with the snapshot date. R1 passes only on a firm's official name; a former or trade name alone makes it `uncertain`. `registry/seed.csv` (4 fictional firms) is the test fixture: it logs a `registry_seed` WARNING if used, and M3 findings then add "(dane demonstracyjne)" (`Registry.demo`: no firm has a `source_url`). Files, source and refresh: [`registry/README.md`](registry/README.md).
- **Privacy:** rule `evidence` and `advertiser` copy scraped author names, handles, profile and referral links verbatim (cut to 200-300 characters) into `findings`, and the `iw:events` messages carry the title, which names the advertiser, so treat them as personal data taken from public posts.
- **Evaluation:** gold-set evaluation (change `analytics-eval-calibration`): `eval/gold.jsonl`, `python eval/run.py`, and the one-shot `analytics-eval` service that feeds the calibration panel (section "Gold-set evaluation" below).

## Modules and routing

A document gives at most one finding per module ([`modules/router.py`](src/investwatch_analytics/modules/router.py), [`pipeline.py`](src/investwatch_analytics/pipeline.py)):

| Who publishes | Registry | Module |
|---|---|---|
| the supervisor or an official register (page or author profile host on `knf.gov.pl`, `uknf.gov.pl`, `gov.pl` or a subdomain; `OFFICIAL_SOURCE_DOMAINS` replaces the list) | — | nothing (`official_source`): it warns about firms, it does not advertise them |
| a registered firm (the page host or the author's profile host is its domain; any platform; a handle alone is not enough) | — | M2 for that firm |
| a foreign firm without a Polish branch (`foreign_no_branch`), its own material | — | nothing (`out_of_scope_m2_foreign_no_branch`): M2 is for firms registered in Poland, including Polish branches |
| `firm_own` source | firm named or page on a firm domain | M2 |
| `firm_own` source | no firm | M3 if an offer signal (S3.3, S3.4, S3.5 or S3.8), else nothing (`no_signals`); service vocabulary alone is no offer |
| a third party | firm named in the text or linked | M1 (a foreign firm without a Polish branch only if the ad targets Poland, else `not_targeting_poland`), plus M3 against the publisher when the advice offer is the publisher's own |
| a third party | no firm | M3 if an offer signal (S3.3, S3.4, S3.5 or S3.8), else nothing (`no_signals`) |

Before routing to a module, the topic gate drops a `third_party` or `unknown` document that has no investment signal: no term of [`gate_terms.yaml`](src/investwatch_analytics/gate_terms.yaml) and no registry firm. With an embedder configured, a document the dictionary would drop, if it has at least `GATE_EMBED_MIN_CHARS` characters, gets a second look. It is embedded and passes when its cosine to the nearest on-topic centroid, minus its cosine to the `off_topic` centroid, is at least `GATE_EMBED_MIN_MARGIN`. The centroids come from the seed lines in `gate_terms.yaml`, and the default margin was measured with `bge-m3` on [`eval/gate_check.jsonl`](eval/gate_check.jsonl): run `python eval/gate_calibrate.py` with `EMBED_BASE_URL` set. Embeddings never re-judge a dictionary pass. Without an embedder, the gate is dictionary-only. The drop is logged as `off_topic` with `dict_hits`, `gate_path`, `similarity` and `margin`, never with text, and counted in Redis `iw:stats:gate` (`passed`, `dropped`, `bypassed`, plus `path_dictionary`, `path_embedding`, `path_dictionary_only_fallback` and `rescued`). `firm_own` documents are never gated. A near-duplicate (MinHash Jaccard ≥ 0.8 over word 5-shingles) is analyzed as usual. Its summary names the original's URL, and it fires no second `finding.high_risk` for its group and module ([ADR 0314](../.docs/decisions/0314-topic-gate-and-near-duplicates.md)).

M1 score: σ(bias + Σ w·x), how certain this is a third-party ad of the firm. M3 score: the same form, capped at 0.4 unless S3.4 (a recommendation to buy, sell or hold financial instruments) is found; M3 means "may indicate" investment advice, and the summary says when personalisation (art. 76) is unconfirmed ([ADR 0308](../.docs/decisions/0308-m3-s34-gate.md)). Signals, weights and dictionaries: [`rules/m1_signals.yaml`](src/investwatch_analytics/rules/m1_signals.yaml), [`rules/m3_signals.yaml`](src/investwatch_analytics/rules/m3_signals.yaml). Evidence may quote the author handle, a link or the page URL as well as the text. Routing and the M1/M3 rules read at most the first 200 000 characters (`SCAN_MAX` in `pipeline.py`); firm names are compared after NFKC and removal of zero-width characters, with quotes cut from the original text. Specs: [`m1-third-party-signals`](../openspec/specs/m1-third-party-signals/spec.md), [`m3-unauthorized-advice-signals`](../openspec/specs/m3-unauthorized-advice-signals/spec.md).

## Run the worker (compose)

The `analytics` service in [`compose.yaml`](compose.yaml) joins the root stack (`docker compose up --build` from the repository root). It needs `postgres`, `redis` (infra) and the one-shot `api-migrate` (api), and builds `DATABASE_URL` (app role `iw_app`) and `REDIS_URL` from the root `.env` (`scripts/init-env.sh`). Feed it a document by hand:

```bash
# after inserting a documents row (the scraper does this, then XADDs)
docker compose exec redis sh -c 'REDISCLI_AUTH="$REDIS_PASSWORD" redis-cli XADD iw:documents "*" document_id <uuid> schema v1'
```

Per message the worker loads the row, runs the pipeline, saves all findings in one transaction, publishes the events and only then acknowledges (XACK). A redelivery or a second message for the same document updates the finding (`(document_id, module)`) and publishes nothing. A malformed message, a missing row or an invalid document is logged and acknowledged; an unexpected error is retried up to `MAX_DELIVERIES`; a Postgres or Redis outage is retried with backoff and never acknowledged. `GET /health` on port 8001 (inside the stack only) answers 200 or 503 with `redis` / `db` flags. Specs: [`document-stream-worker`](../openspec/specs/document-stream-worker/spec.md), [`finding-storage`](../openspec/specs/finding-storage/spec.md), [`finding-events`](../openspec/specs/finding-events/spec.md); design and review follow-ups: [`openspec/changes/archive/2026-11-21-analytics-worker/`](../openspec/changes/archive/2026-11-21-analytics-worker/design.md).

## LLM: hosted DeepSeek or local Ollama

The model is chosen by env only, in the root `.env` (compose passes it to `analytics`; [ADR 0304](../.docs/decisions/0304-llm-serving.md), [ADR 0318](../.docs/decisions/0318-hosted-llm-deepseek-flash.md)). Empty `LLM_BASE_URL` means rules-only. At start-up the worker logs `llm_mode` (`hosted`, `local` or `disabled`) and the model, never the key. If the endpoint fails (timeout, 429, 503, malformed answer), the circuit breaker opens after `LLM_BREAKER_FAILURES` failures and findings are rules-only until it closes; there is no automatic switch to another model.

**Hosted (default): DeepSeek Flash.** Put these in the root `.env`:

```bash
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-flash
LLM_API_KEY=<DeepSeek API key>      # only in .env, never committed
LLM_TIMEOUT_S=60
LLM_DOC_BUDGET_S=90
CLAIM_MIN_IDLE_MS=120000
```

Measured on 2026-11-22: 119 of 120 calls returned valid JSON (one malformed answer, dropped to rules), 3.1 s per call on the gold set and 6.7 s on real pages (p95 18.7 s), and the longest document took 53 s. No `<thought>` block, no fence.

**Hosted alternative: Gemma 4 on the Gemini API** ([ADR 0317](../.docs/decisions/0317-hosted-llm-gemma-on-gemini-api.md)). An open-weights model, but it often returned 503/429 and took 15-40 s per call:

```bash
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
LLM_MODEL=gemma-4-26b-a4b-it        # or gemma-4-31b-it
LLM_API_KEY=<Gemini API key>
LLM_TIMEOUT_S=45
LLM_DOC_BUDGET_S=50
CLAIM_MIN_IDLE_MS=90000
```

**Local: Gemma through Ollama (`--profile llm`).**

1. In the root `.env`, comment out the hosted lines and set:

   ```bash
   LLM_BASE_URL=http://ollama:11434/v1   # internal host on the data network, plain http is allowed
   LLM_MODEL=gemma3:4b
   LLM_API_KEY=ollama                    # any non-empty value; Ollama does not check it
   LLM_TIMEOUT_S=240                     # measured: one 1500-character M1 call took 182 s on CPU
   LLM_DOC_BUDGET_S=300
   CLAIM_MIN_IDLE_MS=360000              # must stay above (LLM_DOC_BUDGET_S + 3 + EMBED_TIMEOUT_S) * 1000 or the worker exits
   LLM_CHUNK_CHARS=1500                  # short chunks: the default 9000 characters take about 6 minutes per call on CPU
   LLM_MAX_CHUNKS=1
   EMBED_BASE_URL=http://ollama:11434/v1 # bge-m3 embeddings; without it bge-m3 is pulled but never used
   ```

   `OLLAMA_PULL_MODELS="gemma3:4b bge-m3"`, `OLLAMA_CONTEXT_LENGTH=8192`, `OLLAMA_MAX_LOADED_MODELS=2` and `OLLAMA_KEEP_ALIVE=30m` come from `.env.example`. A `.env` from before 2026-11-22 may have `OLLAMA_MODEL` or `OLLAMA_MODELS` instead; both are ignored and the defaults apply. Never set `OLLAMA_MODELS`: Ollama reads it as its model directory.

   **Speed on CPU** (measured 2026-11-22 on the demo machine: Docker Desktop with 16 GB and 16 CPUs, no GPU, `ollama` capped at 4 CPUs): `gemma3:4b` reads the prompt at about 10 tokens/s and writes about 1.7 tokens/s. With the values above an M1 check finished in 182 s. An M2 check, which has a longer prompt, still timed out at 240 s and that finding stayed rules-only. While the LLM runs, `bge-m3` calls time out at the default `EMBED_TIMEOUT_S=15` (`model.embedder = null`). With the earlier `LLM_TIMEOUT_S=120` and the default chunk size every call timed out. Locally, expect a few model verdicts per page and the rest rules-only. Hosted, the same call took 4.6 s.

2. Pull the models once (`gemma3:4b` about 3.3 GB, about 7 minutes at 8.5 MB/s; `bge-m3` about 1.2 GB, under 3 minutes), then start the stack with the profile:

   ```bash
   docker compose --profile llm up --exit-code-from ollama-pull ollama-pull   # without --exit-code-from a failed pull still exits 0
   docker compose --profile llm up -d
   # stack already running: recreate only what changed (about 40 s)
   docker compose --profile llm up -d ollama analytics
   ```

   If the pull fails (`unexpected EOF`, `digest mismatch`), run the same command again: finished models are only checked and a broken part is downloaded again. Run one stack only: `ollama` takes up to 6 GB on top of the rest of the stack, and on 2026-11-22 Docker Desktop crashed during a pull with several stacks running at once.

3. Check:
   - `docker compose logs analytics | grep llm_mode` shows `local` and `gemma3:4b`. With `EMBED_BASE_URL` set, `embed_mode` is `local`.
   - `docker compose exec ollama ollama ps` lists `gemma3:4b` and `bge-m3` with `CONTEXT 8192` once each has served a request.
   - Findings decided with the model carry `model.llm = "gemma3:4b"`, and their summary names the model.
   - Re-scanning an unchanged page creates no new document. To send a stored document through analytics again:

     ```bash
     docker compose exec redis sh -c 'REDISCLI_AUTH="$REDIS_PASSWORD" redis-cli XADD iw:documents "*" document_id <document uuid> schema v1'
     ```

**Back to hosted:** restore the hosted lines and limits. Also remove `LLM_CHUNK_CHARS` and `LLM_MAX_CHUNKS`, which are local-only. Either remove `EMBED_BASE_URL` or keep `ollama` running for it (embeddings are local only, ADR 0313). Then run `docker compose up -d analytics` (about 60 s). `ollama` keeps running, so `docker compose stop ollama` frees its memory when embeddings are off.

Notes: the LLM cache key includes the model, so after a switch pages are analysed again. The default thresholds were measured rules-only (ADR 0316), except M1, measured with DeepSeek Flash (ADR 0318); quality on `gemma3:4b` is not measured, and its verdicts differ from the hosted model's (the same Telegram post scored 0.622 with `gemma3:4b` and 0.182 with `gemma-4-26b-a4b-it`).

## Gold-set evaluation (calibration panel)

[`eval/gold.jsonl`](eval/gold.jsonl) holds 69 labeled documents: 35 for M2 (every ZASÓB rule R1-R18 with a violating and a compliant example), 18 for M1 and 18 for M3, about a third of them hard cases. No official sample set was available (`doc/` has the criteria only), so 67 lines are synthetic and 2 are built around phrasings ZASÓB quotes (`origin: zasob-example`); all use fictional firms. The labeling rules are in [`eval/README.md`](eval/README.md).

```bash
.venv/Scripts/python eval/run.py              # JSON report on stdout, rules-only, no database
.venv/Scripts/python eval/run.py --db         # also store the run in calibration_points (DATABASE_URL)
docker compose run --rm analytics-eval        # the same in the stack
```

The one-shot `analytics-eval` service runs `--db` on every `docker compose up`, after `api-migrate`. It stores a module's run only when the gold set, the pipeline version or the results changed, so restarts add nothing. `GET /api/calibration` adds analysts' `confirmed` / `false_positive` labels to that run's counts. The report gives precision, recall and F1 per module on the thresholds 0.05-0.95, counted the same way as the API. Per rule or signal it gives two readings: **`strict` (the headline: `uncertain` counts as not flagged)** and `review` (`uncertain` counts as flagged). Exit codes: 0 ok; 1 a labeled module produced no finding (`not_run`, no rows stored for it) or a gold document crashed the pipeline (nothing stored); 2 invalid gold set or configuration; 3 the database write failed.

Latest numbers (2026-11-22, `main` 0434553b, 69 gold documents): one rules-only run and one run with DeepSeek Flash (`run.py --llm`, recorded in [`eval/llm-run-deepseek-flash.json`](eval/llm-run-deepseek-flash.json)). The plateau is every threshold whose F1 is within 0.02 of the best. Each cell is precision / recall / F1 (tp / fp / fn / tn):

| Module (gold cases: pos / neg) | Default | Rules-only at the default | DeepSeek at the default | Rules-only plateau | DeepSeek plateau |
|---|---|---|---|---|---|
| M1 (18: 10 / 8) | **0.75** | 1.0 / 0.7 / 0.824 (7 / 0 / 3 / 8) | 1.0 / 1.0 / 1.0 (10 / 0 / 0 / 8) | 0.40-0.65, F1 0.889 | 0.75-0.80, F1 1.0 |
| M1 at the old 0.65 | | 1.0 / 0.8 / 0.889 (8 / 0 / 2 / 8) | 0.909 / 1.0 / 0.952 (10 / 1 / 0 / 7) | | |
| M2 (35: 23 / 12) | 0.1 | 0.947 / 0.783 / 0.857 (18 / 1 / 5 / 11) | 0.95 / 0.826 / 0.884 (19 / 1 / 4 / 11) | 0.05-0.10 | 0.10 |
| M3 (18: 10 / 8) | 0.4 (gate cap) | 1.0 / 0.4 / 0.571 (4 / 0 / 6 / 8) | 1.0 / 0.4 / 0.571 (4 / 0 / 6 / 8) | 0.25 only, F1 0.706 | 0.05-0.40, F1 0.588 |

The M2 row is from change `analytics-m2-text-rules` (R9, R10; the DeepSeek run on that branch). Its rules, strict precision / recall: R1 1.0 / 1.0, R2 1.0 / 0.67, R3 0.78 / 1.0, R4 1.0 / 0.5, R6 1.0 / 1.0, R9 1.0 / 0.0 rules-only and 1.0 / 1.0 with DeepSeek (LLM-first: rules-only R9 never fails and its `uncertain` is not scored), R10 1.0 / 1.0, R11, R12a, R12b, R14, R15, R16 and R18 1.0 / 1.0, R17 1.0 / 0.33. R5, R7, R8 and R13 are not built.

M2 slider: at 0.25, 1.0 / 0.609 / 0.757; at 0.40, 1.0 / 0.478 / 0.647, the same on both runs. The DeepSeek run made 28 calls, all valid (3.1 s average, 6.4 s p95).

Rules as `strict` precision / recall, rules-only → DeepSeek where it differs:
- **M1:** S1.1 1.0 / 0.94, S1.2 1.0 / 0.56, S1.3 1.0 / 0.71, S1.4 1.0 / 0.71 → 1.0 / 1.0, S1.5 1.0 / 0 → 1.0 / 1.0, S1.6 1.0 / 1.0, S1.7 1.0 / 0.9.
- **M2:** R1 1.0 / 1.0, R2 1.0 / 0.67, R3 0.78 / 1.0 → 0.88 / 1.0, R4 1.0 / 0.5, R6, R11, R12a, R12b, R14, R15, R16 and R18 1.0 / 1.0, R17 1.0 / 0.33 → 1.0 / 0.67. R5, R7-R10 and R13 are not built.
- **M3:** S3.1 1.0 / 0.53 → 1.0 / 0.47, S3.2 1.0 / 0.43 → 1.0 / 0.29, S3.3 1.0 / 0 → 1.0 / 0.25, S3.4 1.0 / 0 → 1.0 / 0.27, S3.5 1.0 / 0.38, S3.6 1.0 / 0.53 → 1.0 / 0.47, S3.8 1.0 / 1.0.

Without the LLM, S1.5, S3.3 and S3.4 are `uncertain` (`strict` recall 0). M3's default is raised to the S3.4 gate cap (0.4, ADR 0308) so capped findings never alert by default. With DeepSeek, M3's best F1 is lower than rules-only, and 0.4 is on its plateau.

**Default thresholds** ([ADR 0316](../.docs/decisions/0316-default-thresholds-from-evaluation.md), [ADR 0318](../.docs/decisions/0318-hosted-llm-deepseek-flash.md)): M1 0.75, M2 0.1, M3 0.4, written by the API when `iw:settings:thresholds` is missing. [`eval/thresholds.json`](eval/thresholds.json) is the source.
- **M2 and M3** are the rules-only recommendations (M3 raised to its gate cap): `python eval/run.py --write-thresholds` rewrites them.
- **M1** comes from the recorded DeepSeek run, because the hosted LLM is on by default: `LLM_MEASURED_DEFAULTS` in `evaluation/runner.py`, kept by `--write-thresholds`. It is refused if it is not on that run's F1 plateau.
- **Copies.** The API's `DEFAULTS` and `events.DEFAULT_THRESHOLDS` must be copied from the file.
- **Tests.** `tests/test_eval_thresholds.py` fails until the copies match. It also fails when the gold set or M1's rules-only default no longer match the recorded LLM run. Then re-run `python eval/run.py --llm` and replace the run file.

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
| `OFFICIAL_SOURCE_DOMAINS` | `knf.gov.pl,uknf.gov.pl,gov.pl` | comma-separated domains (subdomains included) whose pages never become findings (`official_source`); a value replaces the default; a malformed entry stops the worker and the CLI with exit 2 |
| `DATABASE_URL` | worker: required | Postgres, app role (`postgresql://iw_app:...@postgres:5432/investwatch`) |
| `REDIS_URL` | worker: required | Redis (`redis://:<password>@redis:6379/0`) |
| `WORKER_CONSUMER` | hostname | consumer name in the group `analytics` |
| `STREAM_BLOCK_MS` | `5000` | XREADGROUP block time |
| `CLAIM_MIN_IDLE_MS` | `60000` | XAUTOCLAIM: reclaim a message idle this long (a consumer died) |
| `MAX_DELIVERIES` | `5` | unexpected errors on one message before it is acknowledged as `max_deliveries_exceeded` |
| `HEALTH_PORT` | `8001` | `/health` |
| `MAX_DOCUMENT_BYTES` | `2000000` | a bigger document (`text` + `payload`) is acknowledged as `invalid_document` instead of risking an out-of-memory kill |
| `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY` | empty (rules-only) | the LLM endpoint; hosted and local values in "LLM: hosted Gemma or local Ollama" above, limits (`LLM_TIMEOUT_S`, `LLM_DOC_BUDGET_S`, `LLM_MAX_CHUNKS`, cache and breaker) in [`.env.example`](.env.example) |
| `EMBED_BASE_URL` | empty (off) | OpenAI-compatible embeddings endpoint, local only: `http://ollama:11434/v1` with `docker compose --profile llm up` ([ADR 0313](../.docs/decisions/0313-embeddings-model-and-serving.md)). Off = `model.embedder = null` |
| `EMBED_MODEL`, `EMBED_DIM` | `bge-m3`, `1024` | model and vector size; a vector of another size is rejected (`embed_malformed`). Pull it with `ollama-pull` (issue #65) or by hand: `docker compose exec ollama ollama pull bge-m3`. Measured on CPU (2026-11-22): a cold load takes about 37 s, so the first documents get `model.embedder = null` until the breaker's trial call finds the model loaded; warm calls take 4-12 s. Pre-warm before a demo (one request, or `OLLAMA_KEEP_ALIVE`, issue #65) |
| `EMBED_TIMEOUT_S`, `EMBED_MAX_CHARS`, `EMBED_CACHE_TTL_S`, `EMBED_BREAKER_FAILURES`, `EMBED_BREAKER_COOLDOWN_S` | `15`, `4000`, `604800`, `3`, `60` | per call, input cut, vector cache `iw:emb:v1:*` TTL, circuit breaker. `LLM_DOC_BUDGET_S + 3 + EMBED_TIMEOUT_S` must stay below `CLAIM_MIN_IDLE_MS` |
| `GATE_ENABLED`, `GATE_EMBED_MIN_MARGIN`, `GATE_EMBED_MIN_CHARS` | `true`, `0.03`, `40` | topic gate on/off; the embedding rescue's margin (0-1, on-topic minus off-topic cosine) and the shortest text it embeds. The rescue needs `EMBED_BASE_URL`. `GATE_SIM_THRESHOLD` is no longer read |
| `NEARDUP_NUM_PERM`, `NEARDUP_BANDS`, `NEARDUP_THRESHOLD`, `NEARDUP_MAX_CHARS`, `NEARDUP_TTL_S` | `128`, `32`, `0.8`, `50000`, `2592000` | MinHash near-dup index `iw:neardup:v1:*` in Redis (worker only; the CLI has none) |
| `CONTRACTS_DIR`, `TEST_DATABASE_URL` (or CI's `TEST_DATABASE_ADMIN_URL`), `TEST_REDIS_URL` (or CI's `IW_TEST_REDIS_URL`) | unset | tests only |

## Where things are

- `src/investwatch_analytics/pipeline.py`: `analyze_document(doc, *, registry, catalogue, now, signals, judge, gate, embedder, neardup)` → `Analysis` (findings, gate decision, near-dup group, embedding); `analyze(...)` → its findings. Pure apart from the injected judge, embedder and near-dup index, all off by default.
- `src/investwatch_analytics/gate.py`, `gate_terms.yaml`: the topic gate; `embeddings/`: client, cache, breaker, never-raising embedder; `neardup.py`: MinHash and the Redis LSH index.
- `src/investwatch_analytics/rules/m2_rules.yaml`: all 18 UKNF rules (name, severity, legal basis, dictionaries). Only entries with `implemented: true` run.
- `src/investwatch_analytics/rules/m2.py`: the M2 rule classes: R1 firm identification, R2 ad labeling, R3 risk information next to return claims, R4 and R6 (visual, `blocks`), R11 product comparisons, R12a and R12b past performance (period and scope; currency and costs), R14 past-performance disclaimer, R15 forecasts, R16 tax information, R17 and R18 supervisor mentions. R12a, R12b and R14 share one past-performance detector; each art. 44 element has one owner rule ([ADR 0315](../.docs/decisions/0315-m2-art44-element-ownership.md)). The loader rejects a catalogue pattern with a nested unbounded repetition (ReDoS lint).
- `src/investwatch_analytics/rules/m1.py`, `rules/m3.py`: the M1/M3 signal classes; `modules/m1.py`, `modules/m3.py`: the M1/M3 findings; `modules/advertiser.py`: publisher identity and `advertiser`; `rules/scoring.py`: the sigmoid score.
- `src/investwatch_analytics/worker.py`: the stream consumer (`python -m investwatch_analytics.worker`); `storage.py`: the store interface and the Postgres store; `events.py`: `iw:events` publisher and the live threshold read (ADR 0305); `health.py`: `/health`; `testing.py`: test doubles (`InMemoryStore`, `NoopPublisher`), never imported by the worker.
- `src/investwatch_analytics/evaluation/`: gold-set loader and validation (`gold.py`, `known_ids.py`), metrics with the API's counting (`metrics.py`), runner (`runner.py`), `calibration_points` writer (`store.py`), command line (`__main__.py`); `eval/`: the gold set, its fictional registry and `run.py`.
- Spec: [`openspec/specs/document-analysis/`](../openspec/specs/document-analysis/spec.md) and [`openspec/specs/m2-compliance-rules/`](../openspec/specs/m2-compliance-rules/spec.md); design and review follow-ups: [`openspec/changes/archive/2026-11-21-analytics-skeleton/`](../openspec/changes/archive/2026-11-21-analytics-skeleton/); plan: [`.docs/analytics-plan.md`](../.docs/analytics-plan.md).
