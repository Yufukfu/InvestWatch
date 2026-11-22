# Brief compliance

Each requirement of the challenge brief (`doc/Opis Wyzwania HackNation UKNF 19.11.pdf`, removed before hand-in), with the file or spec that shows it met, or the gap. Section numbers are the brief's. A row says what exists, not how well it works: accuracy numbers are in [presentation-analytics.md](presentation-analytics.md) and [hand-in.md](hand-in.md), the run on real data in [status/scraper.md](status/scraper.md). After a first `docker compose up` run `docker compose run --rm --no-deps -T bootstrap python -m iw_scraper.bootstrap status` ([scraper/README.md](../scraper/README.md)): it exits 0 once every module has a finding.

## 2. Challenge: engine and three modules

| Requirement | Evidence | State |
|---|---|---|
| Central collector for the web and social media | [web collection](../openspec/specs/web-collection/spec.md), [social collection](../openspec/specs/social-collection/spec.md), [X](../openspec/specs/x-collection/spec.md), [YouTube](../openspec/specs/youtube-collection/spec.md) | Web, Telegram, X and YouTube. **Gap:** Facebook, Instagram and TikTok are not collected (login walls and JavaScript shells, [ADR 0103](decisions/0103-first-social-platform.md), [ADR 0109](decisions/0109-social-collectors-research.md)). |
| M1: ads of registered firms posted by third parties: firm, advertiser, content, URL, periodic update | [M1 signals](../openspec/specs/m1-third-party-signals/spec.md), [KNF register loader](../openspec/specs/knf-registry-loader/spec.md), [scan orchestration](../openspec/specs/scan-orchestration/spec.md) (cron) | Done. |
| M2: risk information in firms' own material, flagged automatically | [M2 rules](../openspec/specs/m2-compliance-rules/spec.md), [ADR 0315](decisions/0315-m2-art44-element-ownership.md) | Partly: a subset of the 18 requirements of the annex is implemented, counts in [hand-in.md](hand-in.md). Visual rules need the renderer, off by default. |
| M3: unauthorised advisory services (shadow advisory): entity, offer text, URL | [M3 signals](../openspec/specs/m3-unauthorized-advice-signals/spec.md), [ADR 0308](decisions/0308-m3-s34-gate.md) | Done, rules plus an LLM for doubtful cases. |

## 3. Expected result

| Requirement | Evidence | State |
|---|---|---|
| Job queue on open-source tooling | [ADR 0102](decisions/0102-scraper-job-queue.md) (arq on Redis) | Done. |
| Playwright, httpx and similar | [ADR 0101](decisions/0101-scraper-fetch-client.md), [ADR 0107](decisions/0107-playwright-renderer-service.md), [page rendering](../openspec/specs/page-rendering/spec.md) | Done. |
| Social collectors with User-Agent and proxy rotation | [identities.py](../scraper/src/iw_scraper/identities.py), [proxy.py](../scraper/src/iw_scraper/proxy.py) | Done for the platforms above. |
| Extraction of HTML to JSON | [document ingest](../openspec/specs/document-ingest/spec.md), [contracts](../contracts/README.md) | Done (`ScrapedDocument`). |
| Metadata in SQL, content in SQL plus object storage | [database schema](../openspec/specs/database-schema/spec.md), [shared infrastructure](../openspec/specs/shared-infrastructure/spec.md) | Done (PostgreSQL, MinIO). |
| Cron or orchestrator | [scheduler.py](../scraper/src/iw_scraper/scheduler.py), [first-run bootstrap](../openspec/specs/first-run-bootstrap/spec.md) | Done; the first run needs no manual scan. |
| Preprocessing: HTML removal, normalisation, de-duplication, tokens and embeddings | [document analysis](../openspec/specs/document-analysis/spec.md), [text embeddings](../openspec/specs/text-embeddings/spec.md), [ADR 0314](decisions/0314-topic-gate-and-near-duplicates.md) | Done; embeddings are off unless Ollama runs (`--profile llm`). |
| Inference engine and open model (Ollama, vLLM, Gemma or a classifier) | [ADR 0304](decisions/0304-llm-serving.md), [ADR 0317](decisions/0317-hosted-llm-gemma-on-gemini-api.md), [LLM analysis](../openspec/specs/llm-analysis/spec.md) | Done, with one mentor-approved exception: the default LLM is hosted and swaps to local Ollama by environment only. |
| Scoring function assigns a category | [finding storage](../openspec/specs/finding-storage/spec.md), [ADR 0316](decisions/0316-default-thresholds-from-evaluation.md) | Done. |
| Aggregator merges M1 to M3 into one object | [finding storage](../openspec/specs/finding-storage/spec.md), [contracts](../contracts/README.md) (`Finding`) | Done. |
| Dashboard: filters by date, source, risk level, module | [web findings](../openspec/specs/web-findings/spec.md) | Done. |
| Dashboard: trend charts (Chart.js or Recharts) | [web trend](../openspec/specs/web-trend/spec.md), [ADR 0203](decisions/0203-dashboard-charts-recharts.md) | Done (Recharts). |
| Alerts: record status change; WebSocket notifications of high risk | [web alerts](../openspec/specs/web-alerts/spec.md), [event relay](../openspec/specs/event-relay/spec.md), [ADR 0208](decisions/0208-dashboard-realtime-socketio-client.md) | Done (Socket.IO). |
| Calibration panel: threshold changes false positives against false negatives | [web calibration](../openspec/specs/web-calibration/spec.md), [gold-set evaluation](../openspec/specs/gold-set-evaluation/spec.md), [ADR 0305](decisions/0305-threshold-storage.md) | Done on a synthetic gold set. **Gap:** UKNF samples were not available, so the curve is not measured on real labels. |
| UI libraries allowed, props-based architecture | [ADR 0204](decisions/0204-frontend-architecture.md) | Done. |

## 5. Technical requirements

| Requirement | Evidence | State |
|---|---|---|
| Light modular services, no heavy monorepo | [README.md](../README.md) (structure), [ADR 0202](decisions/0202-deployment-topology.md) | Done. |
| Docker and Compose, whole stack on-premise with one command | [compose.yaml](../compose.yaml), [infra/README.md](../infra/README.md) | Done; the first run fills itself ([first-run bootstrap](../openspec/specs/first-run-bootstrap/spec.md)). |
| Open source and on-premise, no paid external API | [ADR 0304](decisions/0304-llm-serving.md) | Done except the hosted-LLM exception above. |
| Dependency scanning, secrets only in `.env` | [supply-chain.md](supply-chain.md), [security-audit.md](security-audit.md), [ADR 0209](decisions/0209-supply-chain-scanning.md), [supply-chain scanning](../openspec/specs/supply-chain-scanning/spec.md) | Done; results are in each PR body. |
| README: Quick Start, hardware requirements, service configuration | [README.md](../README.md) | Done. |

## 6. What the jury checks

| Item | Evidence | State |
|---|---|---|
| Scraping effectiveness | [status/scraper.md](status/scraper.md) (demo rehearsal), [scrape report](../openspec/specs/scrape-report/spec.md) | Measured on 17 seeded sources. **Gap:** scheduled scans are not recorded end to end. |
| Risk classification accuracy and calibration effect | [presentation-analytics.md](presentation-analytics.md), [demo-analytics.md](demo-analytics.md) | Gold-set numbers are synthetic. |
| Stable interface and real-time alerts | [web foundation](../openspec/specs/web-foundation/spec.md), [web alerts](../openspec/specs/web-alerts/spec.md) | Tested; stability under the demo is the rehearsal's job. |
| Libraries and their security | [supply-chain.md](supply-chain.md) | See above. |
| `console.log` | [git-guard.js](../.claude/hooks/git-guard.js) refuses it in commits | Enforced by a hook. |

## 4. Hand-in

Title, description, PDF, README, repository and the optional video: [hand-in.md](hand-in.md).
