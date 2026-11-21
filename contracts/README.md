# Contracts v1

Single source of truth for data exchanged between the scraper, analytics, API and dashboard. Background and rationale: [`doc/integration-plan.md`](../doc/integration-plan.md).

| File | Used by | Describes |
|---|---|---|
| `schemas/scraped-document.schema.json` | scraper → analytics, API | a collected document (`documents` table) |
| `schemas/finding.schema.json` | analytics → API → dashboard | an analysis result (`findings` table) |
| `schemas/source.schema.json` | scraper, API, dashboard | a scraping source (`sources` table) |
| `schemas/events.schema.json` | all | Redis Stream messages and Socket.IO events |
| `openapi.yaml` | API ↔ dashboard | REST endpoints (OpenAPI 3.1, references the schemas above) |
| `mocks/*.json` | dashboard, tests | example responses for every endpoint and event |

## Mock data

All firms, people, handles and URLs in the mocks are **fictional**. Mock file ↔ endpoint:

| Mock | Endpoint / channel |
|---|---|
| `findings.json` | `GET /api/findings` |
| `finding-detail.json` | `GET /api/findings/{id}` |
| `summary.json` | `GET /api/stats/summary` |
| `trend.json` | `GET /api/stats/trend` |
| `calibration-M1.json`, `-M2`, `-M3` | `GET /api/calibration?module=…` |
| `thresholds.json` | `GET /api/settings/thresholds` |
| `sources.json` | `GET /api/sources` |
| `health.json` | `GET /api/health` |
| `events.json` | Socket.IO `/events` (sequence of events) |
| `documents.json` | rows of the `documents` table (scraper output) |

Regenerate after changing a scenario: `python contracts/mocks/generate_mocks.py` (deterministic – same UUIDs every run).

## Validation

```
pip install -r contracts/requirements.txt
python contracts/validate.py                  # all mocks + referential integrity + OpenAPI parse
python contracts/validate.py document out.json   # check scraper output against the contract
python contracts/validate.py finding out.json    # check analytics output against the contract
```

Run it before merging any change to `contracts/`.

## Changing a contract

1. Propose the change (OpenSpec change proposal) and agree it with the affected owners (A, B, C).
2. Update the schema, `openapi.yaml`, the mock generator and regenerate mocks.
3. `python contracts/validate.py` must pass.
4. Breaking changes bump the version (`v2`) in the stream message `schema` field.
