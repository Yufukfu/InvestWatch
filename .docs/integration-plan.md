# InvestWatch – Module Integration Plan

Contract version: **v1** (frozen at 14:30 on Saturday; changes only after team agreement and with a version bump).

## Team and responsibilities

| Person | Module | Owns |
|---|---|---|
| **Adam** | Scraper | collectors (web + social media), job queue, scheduler, writes to `documents` + objects in MinIO |
| **Kacper** | Dashboard | frontend, filters, charts, WebSocket alerts, calibration panel; **repository structure** |
| **Damian** | Analytics + integration | database schema, contracts, REST API + WebSocket gateway, modules M1–M3, firm registry, docker-compose |

Decisions from the team sync:

- ✅ **Damian builds the REST API** (a thin layer over the same database). Kacper works against mock data matching the contract in section 5 from the start; Adam focuses only on data collection.
- ✅ **Social media:** we start with **one platform** and add more only if time allows.
- ✅ **LLM:** accessed through an HTTP API; for the hackathon a hosted OpenAI-compatible model, with local Gemma as the env-only swap target ([ADR 0304](decisions/0304-llm-serving.md), note in section 7).
- ✅ **Repository structure** is defined by Kacper; the layout below is only the list of services that must exist.
- ✅ **Spec-driven workflow with OpenSpec** + an AI work log (`.docs/ai-workflow.md`).
- ⏳ Contracts (sections 3–6) – to be confirmed by Adam and Kacper.
- ⏳ Rendering metadata from the scraper (`blocks`, screenshots) – to be discussed with Adam later.
- ⏳ Milestone hours and the sleep rotation – to be agreed.

## 1. Architecture

```
                ┌──────────────┐  XADD iw:documents   ┌──────────────────┐
 scheduler ────▶│  scraper (Adam) │ ───────────────────▶ │  analytics (Damian)   │
 (cron/beat)    │ Playwright,  │                      │ preprocessing,   │
                │ httpx, UA/   │──┐                ┌──│ M1/M2/M3, LLM    │
                │ proxy rotation  │                │  └────────┬─────────┘
                └──────────────┘  │ INSERT         │ INSERT    │ PUBLISH iw:events
                                  ▼                ▼           ▼
                      ┌────────────────────┐   ┌──────────┐  ┌────────────────┐
                      │ PostgreSQL         │   │ MinIO    │  │ api (Damian)        │
                      │ sources, documents,│   │ html,    │  │ FastAPI REST + │
                      │ findings, registry │   │ screens  │  │ Socket.IO      │
                      └─────────▲──────────┘   └──────────┘  └───────┬────────┘
                                └──────────────── SELECT ────────────┤
                                                                      ▼
                                                            ┌────────────────┐
                                                            │ dashboard (Kacper)  │
                                                            └────────────────┘
                     LLM endpoint (OpenAI-compatible API: hosted, or local Gemma via Ollama) ◀── analytics
```

Services in the root `compose.yaml`, which only `include:`s each module's own `compose.yaml` ([ADR 0202](decisions/0202-deployment-topology.md); single `docker compose up` command):
`postgres`, `redis`, `minio` (+ one-shot `minio-init`), `gateway` from `infra/`, then `scraper`, `scheduler`, `analytics`, `api`, `web` as each module adds its file (+ `ollama` behind the compose profile `llm`, the local LLM fallback from ADR 0304). Object storage is MinIO built by Chainguard, because upstream no longer publishes images ([ADR 0306](decisions/0306-object-storage-image.md)). How a module joins: [`infra/README.md`](../infra/README.md).

Required service folders (exact layout per Kacper): `scraper` (Adam), `analytics` (Damian), `api` (Damian), `dashboard` (Kacper), `contracts` (Damian – JSON Schema + mock data), `.docs` (plans, ADRs, AI work log), `doc` (UKNF materials in Polish, removed before hand-in), plus `compose.yaml` (include list) and `.env.example` at the root.

## 2. Integration points

| # | From → to | Mechanism | Payload |
|---|---|---|---|
| 1 | scraper → database | `INSERT` into `documents` | document per the `ScrapedDocument` schema (section 3) |
| 2 | scraper → MinIO | bucket `iw-raw` | `html/{document_id}.html`, `shot/{document_id}/{viewport}.png`, `media/{document_id}/{n}.{ext}` |
| 3 | scraper → analytics | Redis Stream `iw:documents` | `{"document_id": "<uuid>", "schema": "v1"}` – published **after** the DB commit |
| 4 | analytics → database | `INSERT` into `findings` | result per the `Finding` schema (section 4) |
| 5 | analytics → API | Redis Pub/Sub `iw:events` | events (section 6) |
| 6 | API → dashboard | REST + Socket.IO | sections 5 and 6 |
| 7 | analytics → LLM | HTTP `LLM_BASE_URL` | generation and embeddings |

A Redis Stream with an `analytics` consumer group gives us: independence from the scraper's language, retries (`XPENDING`/`XCLAIM`) and the option to run several analytics workers. The scraper does not need to know anything about analytics.

## 3. Contract: `ScrapedDocument` (scraper → analytics)

Table `documents`; simple columns + `payload JSONB` for the rest.

```jsonc
{
  "id": "uuid",
  "source_id": "uuid",                  // row in the sources table
  "platform": "web|facebook|instagram|tiktok|youtube|x|forum|other",
  "source_kind": "firm_own|third_party|unknown", // published by the firm itself (M2) or by someone else (M1/M3)
  "url": "https://...",
  "canonical_url": "https://...",
  "fetched_at": "2026-11-21T14:05:00Z",
  "published_at": "2026-11-20T09:00:00Z | null",
  "http_status": 200,
  "lang": "pl | null",                  // optional – analytics detects it anyway
  "title": "string | null",
  "text": "clean text of the whole material",
  "content_hash": "sha256 of normalized text", // deduplication
  "author": {                           // for social media / blogs
    "name": "string | null",
    "handle": "@nick | null",
    "profile_url": "https://... | null",
    "followers": 12345
  },
  "links": [ { "href": "https://...", "text": "string", "rel": "nofollow sponsored | null" } ],
  "media": [ { "type": "image|video", "object_key": "media/...", "alt": "string | null" } ],
  "html_object_key": "html/{id}.html | null",
  "screenshots": { "desktop": "shot/{id}/desktop.png", "tablet": "...", "mobile": "..." },

  // Only for web pages rendered with Playwright – needed for the visual M2 rules (R4–R8, R13)
  "blocks": [
    {
      "viewport": "desktop|tablet|mobile",
      "text": "Invest with returns of up to 20% a year",
      "tag": "h1|p|span|small|footer|...",
      "font_size_px": 32,
      "font_weight": 700,
      "color": "#111111",
      "background_color": "#ffffff",
      "bbox": [x, y, w, h],
      "visible": true,                  // display/visibility/opacity/size > 0
      "in_viewport_on_load": true,      // visible without scrolling
      "requires_interaction": false,    // hidden in <details>, accordion, tooltip, modal
      "region": "main|header|footer|legal|aside|overlay",
      "overflow_clipped": false         // text clipped (responsiveness)
    }
  ],
  "scrape_meta": { "scraper": "playwright|httpx|api", "user_agent": "...", "proxy": "id | null", "duration_ms": 1830 }
}
```

Machine-readable versions of all contracts in this document (JSON Schema, OpenAPI, mocks): [`contracts/`](../contracts/README.md).

Minimum required for analytics to work: `id, platform, url, fetched_at, text, source_kind`.
`author` is optional and is set only by a platform collector from the platform's own account fields (for example the channel handle the platform renders), never from claims the post's writer controls on a page (`<meta>`, `rel=author`, embedded JSON), because analytics' publisher match (`analytics-m1-m3`, PR #35) routes on `author.handle` / `author.profile_url`, and on the host of `url`, which must stay the guarded fetch URL, never a value from markup. No `web` source sets it today; absent means unknown, not "third party". Per-platform provenance: [`scraper/README.md`](../scraper/README.md), "Author provenance".
`blocks` and `screenshots` are required only for the visual rules; without them rules R4–R8 and R13 get `not_applicable`, never a false "pass".

Table `sources` (managed by the scraper, editable from the dashboard):
`id, name, platform, url, source_kind, target_modules ["M1","M2","M3"], schedule_cron, active, last_run_at, last_run_status (ok|partial|failed|running)`.
The scraper writes only `last_run_at` and `last_run_status`. `documents_count` in the `Source` contract ([`source.schema.json`](../contracts/schemas/source.schema.json)) is not a column: the API counts the source's `documents` rows on read (total, not the last job).

## 4. Contract: `Finding` (analytics → database → API)

One document can produce 0–3 findings (one per module).

```jsonc
{
  "id": "uuid",
  "document_id": "uuid",
  "module": "M1|M2|M3",
  "score": 0.87,                        // raw score 0–1; the threshold is NOT stored – the API derives risk_level, analytics only uses it to emit finding.high_risk (ADR 0305)
  "status": "new|in_review|confirmed|false_positive|closed",
  "title": "EuroTrade Markets ad by finfluencer @inwestor_jan without an ad label",
  "summary": "2–3 sentence rationale (in Polish – user-facing)",
  "firm": {                             // investment firm the material concerns (M1, M2)
    "name": "EuroTrade Markets Ltd (Polish branch)",   // fictional example
    "registry_id": "uuid | null",
    "registry_type": "brokerage_house|brokerage_bank|foreign_branch|foreign_no_branch|null",
    "authorized": true,
    "match_confidence": 0.93
  },
  "advertiser": {                       // advertising / offering party (M1, M3)
    "name": "Jan Kowalski",
    "handle": "@inwestor_jan",
    "profile_url": "https://...",
    "in_registry": false
  },
  "rules": [                            // M2: the 18 UKNF rules; M1/M3: signals
    {
      "rule_id": "R3",
      "name": "Risk information",
      "result": "fail|pass|not_applicable|uncertain",
      "severity": "high|medium|low",
      "evidence": "exact quote from the document",
      "evidence_locator": { "viewport": "desktop", "bbox": [0,0,0,0] },
      "explanation": "A 20% return claim without a nearby risk warning.",
      "legal_basis": "Art. 44(2)(b) Delegated Regulation (EU) 2017/565"
    }
  ],
  "content_excerpt": "content snippet for the table",
  "url": "https://...",                 // denormalized for the dashboard
  "platform": "instagram",
  "detected_at": "2026-11-21T14:06:10Z",
  "updated_at": "2026-11-21T14:06:10Z",
  "model": { "pipeline_version": "0.3.0", "llm": "gemma-3-4b", "embedder": "bge-m3" }
}
```

The API derives `risk_level` from the threshold: `high` ≥ module threshold, `medium` ≥ threshold − 0.2, otherwise `low`.

## 5. REST API (API → dashboard)

Base URL `/api`, JSON, pagination `?page=1&page_size=50`.

| Method | Path | Description |
|---|---|---|
| GET | `/findings` | list; filters: `module, status, platform, source_id, risk_level, score_min, date_from, date_to, q` |
| GET | `/findings/{id}` | details + `document` (text, links, screenshot URLs) |
| PATCH | `/findings/{id}` | `{ "status": "...", "note": "..." }` – status change (alerting requirement) |
| GET | `/stats/trend` | `?module&bucket=hour|day&risk_level&date_from&date_to` → `{ "bucket": "hour", "points": [{ "t": "...", "M1": 3, "M2": 7, "M3": 1 }] }` (shape in `contracts/openapi.yaml`); day buckets start at 00:00 UTC (to confirm with Damian) |
| GET | `/stats/summary` | counts per module / status / platform |
| GET | `/calibration` | `?module=M2` → curve: `[{ "threshold": 0.5, "tp": 12, "fp": 4, "fn": 2, "tn": 30, "precision": 0.75, "recall": 0.86 }]` |
| GET / PUT | `/settings/thresholds` | `{ "M1": 0.6, "M2": 0.5, "M3": 0.7 }` – changing a threshold recomputes `risk_level`. Stored by the API in Redis key `iw:settings:thresholds` as a JSON string of exactly this shape (defaults written when missing: the gold-set evaluation's best-F1 thresholds, today 0.65 / 0.1 / 0.4, ADR 0316); analytics reads the same key (ADR 0305) |
| GET / POST / PATCH | `/sources` | list and edit sources |
| POST | `/scans` | `{ "source_id": "..." }` – manually trigger a scan (XADD to `iw:scan-requests`). The scraper owns the consumer side: its consumer group on `iw:scan-requests` runs the scan and publishes `scan.started` / `scan.finished` on `iw:events` (§6). Until the scraper reads the stream, the request is queued and nothing runs |
| GET | `/documents/{id}/screenshot/{viewport}` | screenshot preview from MinIO |
| GET | `/health` | service status (for the demo) |

Calibration: TP/FP/FN are the sum of findings labeled by analysts (`confirmed` / `false_positive`) and the latest **gold-set** run stored in `calibration_points` by the analytics evaluation (file `analytics/eval/gold.jsonl`, not a table; ADR 0312). This way the threshold slider shows precision and recall changing live, and a few labels never replace the gold curve.

## 6. Real-time events

Redis Pub/Sub `iw:events` → API → Socket.IO (namespace `/events`, path `/socket.io`, same origin through the gateway). Each message is `{ "type", "emitted_at", "data" }` (`contracts/schemas/events.schema.json`); the API forwards `data` unchanged under the event name `type` and drops messages that fail the schema (only a log warning, so a producer bug shows up as missing alerts). For `finding.created` / `finding.high_risk`, `data` is exactly `{ id, module, score, title, url, platform }` plus an optional `risk_level`, no other keys:

| Event | Payload | When |
|---|---|---|
| `finding.created` | `{ id, module, score, title, url, platform }` | every new finding |
| `finding.high_risk` | same | published by analytics when `score` ≥ the module threshold in Redis `iw:settings:thresholds` at creation time (ADR 0305) → toast/alert |
| `finding.updated` | `{ id, status }` | published by the API on `iw:events` after `PATCH /findings/{id}` commits (status or note change; sync between tabs) |
| `scan.started` / `scan.finished` | `{ source_id, documents, status }`: `documents` = new documents of that job (integer or null), `status` = `ok\|partial\|failed` or null ([`events.schema.json`](../contracts/schemas/events.schema.json)) | scan progress bar |

## 7. Shared conventions

- Time is always UTC ISO-8601; UUID v4 identifiers are generated by the record's producer.
- Configuration only through environment variables (`.env`; only `.env.example` in the repo): `DATABASE_URL, REDIS_URL, MINIO_*, LLM_BASE_URL, LLM_API_KEY, LLM_MODEL, EMBED_MODEL, PROXY_LIST, USER_AGENTS_FILE`.
- **LLM note:** the task PDF asks for an on-premise, open-source stack with no external paid APIs; the mentors allowed a hosted provider for the hackathon if the code swaps easily to open-source models ([ADR 0304](decisions/0304-llm-serving.md)). Analytics calls an **OpenAI-compatible HTTP API** configured by `LLM_*` env only: a hosted provider during development, or local Gemma (`gemma3:4b`) through the optional `ollama` compose profile, which Ollama serves under `/v1`. The hand-in README names the mentor exception and the local fallback, because the jury checks compliance with the specified technologies.
- Database migrations in one place (Alembic in `api`) – Adam and Damian never create tables by hand.
- Every service: `/health`, JSON logs to stdout, zero `console.log` in the production frontend build.
- Dependencies: `npm audit` / `pip-audit` before every merge to `main`; results in `.docs/security-audit.md`.
- Branches: `scraper/*`, `dashboard/*`, `analytics/*`; merge to `main` only with a working `docker compose up`.
- **Technical documentation, code, comments and commit messages are in English.** User-facing dashboard texts and finding summaries are in Polish.

## 8. Integration milestones

Submission deadline: **Sunday 22.11, 11:00**. Buffer: we submit at 10:30. Hours below are a proposal (⏳ to be agreed).

| When | Milestone | Evidence |
|---|---|---|
| Sat 14:30 | **Contracts v1 frozen** | `contracts/*.schema.json`, mocks `findings.json`, `documents.json`; docker-compose with postgres/redis/minio starts |
| Sat 17:00 | **Integration #1 – "thin thread"** | Adam pushes 1 real document → Damian creates a finding (even rule-based only) → Kacper sees it in the table and gets a WS alert |
| Sat 22:00 | **Integration #2 – all modules** | ≥ 1 source each for M1, M2, M3; filters, trend and status change work on real data |
| Sun 03:00 | **Integration #3 – calibration** | the threshold slider changes FP/FN on the gold set; the scheduler scans periodically |
| Sun 08:00 | **Feature freeze** | fixes only; dependency audit, README, clean console |
| Sun 10:30 | **Submission** | repo, PDF, README, video (optional) |

At every milestone: a 10-minute sync of all three – what works end-to-end, what blocks, whether we change the contract.
