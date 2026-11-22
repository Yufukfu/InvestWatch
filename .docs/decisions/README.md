# Architecture decision records

One file per decision: `NNNN-short-title.md`, copied from `0000-template.md`. Numbers come from the owner's range so parallel PRs never collide: Adam `01xx`, Kacper `02xx`, Damian `03xx`. ADRs are written by agents in the same PR as the change they record (or in an earlier docs-only PR that the implementing PR links), with the decision and a rationale that cites evidence; each is committed with `Status: accepted` and takes effect when the human approves and merges the PR; the Status column below shows it. Never auto-merge an ADR. An accepted ADR is not edited: a new ADR supersedes it and links the old one. Write one when a choice is hard to reverse or a teammate will ask "why".

Every ADR file must be listed in the table below (checked by `docs-check.mjs`).

| ADR | Decision | Status |
|---|---|---|
| [0101](0101-scraper-fetch-client.md) | Scraper fetch client | accepted (agent-written; effective on merge) |
| [0102](0102-scraper-job-queue.md) | Scraper job queue and scheduler | accepted (agent-written; effective on merge) |
| [0103](0103-first-social-platform.md) | First social platform | accepted (agent-written; effective on merge) |
| [0104](0104-ingest-order-and-republish-sweep.md) | Ingest order, at-least-once delivery and the republish sweep | accepted (agent-written; effective on merge) |
| [0105](0105-content-hash-normalisation.md) | One `content_hash` normalisation: NFC (the scraper's), written into integration-plan §3 | accepted (agent-written; effective on merge) |
| [0106](0106-scraper-deployment-unit.md) | Scraper deployment unit: three services, networks, stop grace, merge order with the renderer | accepted (agent-written; effective on merge) |
| [0107](0107-playwright-renderer-service.md) | Playwright renderer as a separate, hardened service (`--no-sandbox`, Chromium 147 pin) | accepted (agent-written; effective on merge) |
| [0108](0108-source-discovery-candidates.md) | Source discovery: inactive candidate sources mined from stored links, approved by a human | accepted (agent-written; effective on merge) |
| [0109](0109-social-collectors-research.md) | Social collectors for X and YouTube: X posts through a cookie-based library with a dedicated account, YouTube metadata through our fetcher, transcripts through `youtube-transcript-api` on a residential proxy (local speech-to-text on audio as the proven fallback) (probes, evidence, the robots.txt and login exception) | accepted (agent-written; effective on merge) |
| [0201](0201-web-stack-and-generated-client.md) | Dashboard stack: React + RTK Query client generated from the OpenAPI contract, MSW mocks | accepted; dev mocks superseded by [0206](0206-dashboard-data-from-backend.md) |
| [0202](0202-deployment-topology.md) | Per-module compose, Caddy HTTPS gateway, Postgres on an internal network | accepted; ownership of `infra/` and the include list superseded by [0211](0211-codeowners-single-source.md) |
| [0203](0203-dashboard-charts-recharts.md) | Dashboard charts: Recharts (the only chart library in `web/`) | accepted (takes effect when PR merges) |
| [0204](0204-frontend-architecture.md) | Frontend layering: feature data hooks wrap the generated client, components take props | accepted (takes effect when PR merges) |
| [0205](0205-status-per-domain.md) | Status split per domain: `.docs/STATUS.md` team-wide only, one file per owner in `.docs/status/` | accepted; domains mapped to people superseded by [0211](0211-codeowners-single-source.md) |
| [0206](0206-dashboard-data-from-backend.md) | Dashboard data from the backend only; MSW only in tests (supersedes 0201's dev mocks) | accepted (takes effect when PR merges) |
| [0207](0207-agent-push-and-pr.md) | Agents push their branch and open the PR; humans approve and merge | accepted (takes effect when the PR merges) |
| [0208](0208-dashboard-realtime-socketio-client.md) | Dashboard real-time client: socket.io-client, one connection owned by the alerts feature | accepted (takes effect when the `realtime-alerts` PR merges) |
| [0209](0209-supply-chain-scanning.md) | Verifiable supply chain: `npm audit` + `pip-audit` + offline OSV-Scanner, Gitleaks for hard-coded secrets, no vendor SaaS (Snyk rejected) | accepted (takes effect when the PR merges) |
| [0210](0210-unattended-pr-watcher.md) | An unattended PR watcher runs sandboxed agent sessions and publishes from the runner | accepted (takes effect when PR #48 merges; needs Adam's and Damian's approval) |
| [0211](0211-codeowners-single-source.md) | `.github/CODEOWNERS` is the only place that names owners; shared areas have none (partly supersedes 0202 and 0205) | accepted (takes effect when the `codeowners-single-source` PR merges) |
| [0301](0301-contracts-v1.md) | Confirmation of data contracts v1 | accepted (takes effect when PR #3 merges) |
| [0302](0302-api-service.md) | Placement and stack of the REST/WebSocket API | accepted (takes effect when PR #3 merges) |
| [0303](0303-database-schema-ownership.md) | Ownership of the database schema and migrations (depends on [0302](0302-api-service.md)) | accepted (takes effect when PR #3 merges) |
| [0304](0304-llm-serving.md) | How Gemma is served to analytics | accepted (takes effect when PR #3 merges) |
| [0305](0305-threshold-storage.md) | Where module thresholds live and who emits `finding.high_risk` | accepted; default values superseded by [0316](0316-default-thresholds-from-evaluation.md) |
| [0306](0306-object-storage-image.md) | Object storage and Redis images: Chainguard MinIO build, Redis 8 from the ECR mirror | accepted (takes effect when the `infra-compose` PR merges) |
| [0307](0307-database-driver-and-table-layout.md) | Database driver (psycopg 3) and table layout (columns + JSONB, dedup and upsert keys) (depends on [0303](0303-database-schema-ownership.md)) | accepted (takes effect when the `api-db-schema` PR merges) |
| [0309](0309-llm-prompt-and-cache-contract.md) | LLM prompt, response and cache contract; the LLM decides only checks the rules defer (depends on [0304](0304-llm-serving.md)) | accepted (takes effect when the `analytics-llm-p0` PR merges) |
| [0310](0310-llm-chunking-and-budget.md) | LLM chunking on sentence boundaries, worst chunk wins, per-document budget below the claim idle time (depends on [0304](0304-llm-serving.md)) | accepted (takes effect when the `analytics-llm-p0` PR merges) |
| [0308](0308-m3-s34-gate.md) | M3 gate: a recommendation of instruments alone lifts the 0.4 cap ("may indicate" advice, personalisation unconfirmed) | accepted (takes effect when PR #35 merges) |
| [0311](0311-knf-registry-source-and-ids.md) | KNF registry: HTML lists parsed by a manual loader, committed `registry/knf.csv`, uuid5 firm ids | accepted (takes effect when the `analytics-knf-registry` PR merges) |
| [0312](0312-gold-set-evaluation.md) | Gold-set evaluation feeds the calibration panel: fictional eval registry, strict/review readings, idempotent default-stack run, labels plus gold in the API | accepted (takes effect when the `analytics-eval-calibration` PR merges) |
| [0313](0313-embeddings-model-and-serving.md) | Embeddings: `bge-m3` on the local `ollama` service through OpenAI-compatible `/v1/embeddings`, env-only, no hosted default (depends on [0304](0304-llm-serving.md)) | accepted (takes effect when the `analytics-embeddings` PR merges) |
| [0314](0314-topic-gate-and-near-duplicates.md) | Topic gate (dictionary or embedding, drop only when both say no) and near-dups (MinHash, analyzed and grouped, never dropped) (depends on [0313](0313-embeddings-model-and-serving.md)) | accepted (takes effect when the `analytics-embeddings` PR merges) |
| [0315](0315-m2-art44-element-ownership.md) | M2: one owner rule per art. 44 element (count once); R15 reports every detected forecast, R11 flags only violations | accepted (takes effect when the `analytics-m2-p1-rules` PR merges) |
| [0316](0316-default-thresholds-from-evaluation.md) | Default thresholds from the gold-set evaluation (best F1 per module, rules-only; supersedes 0305's default values only) | accepted (takes effect when the `analytics-eval-calibration` PR merges) |
| [0317](0317-hosted-llm-gemma-on-gemini-api.md) | Hosted LLM default: Gemma 4 on the Gemini API (OpenAI-compatible endpoint); supersedes only ADR 0304's provider choice | accepted (takes effect when the `analytics-llm-p0` PR merges) |

## Candidate topics (evidence only, rationale to be decided by a human)

- **First social platform** (team decision: one platform first). Lead: Adam.
