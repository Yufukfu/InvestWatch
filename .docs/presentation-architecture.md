# Presentation: architecture and scale-out (2 slides)

Slide content for the hand-in PDF (issue #74). Kacper pastes it into the deck next to `presentation-analytics.md` and the scraper slides (PR #98); each `##` below is one slide, with speaker notes under **Notes**. Written for Kacper (infra).

Every name and arrow was checked on `main` at `082736c` (2026-11-22) against `docker compose --profile llm config` (services, networks, ports) and the producer and consumer code of each Redis key. The scale-out numbers are from the runs in `openspec/changes/archive/2026-11-22-architecture-scale-out/evidence.md`. Refresh the services and networks with `docker compose --profile llm config --format json`.

---

## 1. Independent modules, one `docker compose up`, one open door

Every module is its own container image with its own `compose.yaml`; the root file only `include:`s them (ADR 0202). The modules never import each other: they meet through Redis, Postgres, object storage and REST.

```
 internet ─HTTPS :8443─▶ gateway (Caddy, TLS) ──── only service with a host port ────────────────
                          │ /api, /socket.io           │ /                       [edge network]
                          ▼                            ▼
   dashboard ◀─REST + Socket.IO─ api (FastAPI)       web (static SPA)
   (browser)                  │  ▲ SUBSCRIBE iw:events
 ─────────────────────────────┼──┼───────────────────────────────────────────────────────────────
  [data network: internal, no route to the internet]    │ XADD iw:scan-requests (POST /api/scans)
                              │  │                      ▼
  scheduler ──arq jobs──▶ ┌───┴──┴─────────────────────────────┐        ┌───────────┐
  (exactly one)           │ redis   streams iw:documents,      │◀──────▶│ worker ×N │──┐ [render net]
                          │         iw:scan-requests, pub/sub  │        │ scraper   │  ▼ internal
                          │         iw:events, key thresholds  │        └─┬───┬─────┘ renderer
                          └───────────────▲────────────────────┘          │   │       (Playwright,
                                          │ XREADGROUP (group analytics)  │   │        optional)
                          ┌───────────────┴────────┐  INSERT documents    │   │ PUT html
                          │ analytics ×M           │◀─────────────────────┘   │
                          │ rules M1/M2/M3 + LLM   │      ┌───────────────┐   │
                          │ INSERT findings,       │─────▶│ postgres      │   │
                          │ PUBLISH iw:events      │      └───────────────┘   ▼
                          └──────┬─────────────────┘      ┌───────────────┐  minio (bucket iw-raw)
                                 │ LLM_BASE_URL            │               │
  ─ [egress network: internet] ──┼─────────────────────────┴───────────────┴──────────────────────
     worker ─▶ target sites      ▼
     analytics ─▶ hosted DeepSeek Flash (default)   or, same code, env only:  ollama (profile llm, data network only)
```

- **Networks:** `edge` (gateway, `api`, `web`), `data` (internal, no internet: Postgres, Redis, MinIO, Ollama, `api`, `worker`, `scheduler`, `analytics` and the one-shots `api-migrate`, `minio-init`, `seed`, `analytics-eval`), `egress` (internet: `worker`, `analytics`, `renderer`, `ollama-pull`) and `render` (internal, `worker` to `renderer` only). Each service sits on only the networks it needs.
- **Flows:** `scheduler` and `api` (a manual scan) feed the `worker` queue; the `worker` writes the page to Postgres and MinIO and announces `document_id` on `iw:documents`; `analytics` reads it as a consumer group, writes findings to Postgres and publishes events; `api` relays them to the browser. One-shots not drawn: `api-migrate` (schema), `minio-init` (bucket), `seed` (sources), `analytics-eval` (gold-set run), `ollama-pull` (model download).
- **Open to extension:** a rule is a YAML entry plus a class and a collector is a registry entry (slides in `presentation-analytics.md` and the scraper slides, PR #98); a new module is one `compose.yaml` and one `include:` line (`infra/README.md`, "Joining the stack").

**Notes:** Why this shape: three people edited in parallel, so each owns a directory and a compose file and the only shared things are network contracts (ADR 0202). Why the networks: the one door is the gateway; the data stores sit on a network with no route out, and the only containers that reach the internet are the ones whose job it is (fetching pages, calling the hosted model, pulling model weights). Ollama's API has no authentication, so it is on `data` only and its model download runs in a separate one-shot on `egress`. The hosted LLM is a mentor-approved exception to on-premise (ADR 0304); the same container runs the local Gemma when `LLM_BASE_URL` points at `ollama`. Sources: `compose.yaml`, `infra/compose.yaml`, `*/compose.yaml`, `infra/README.md`, ADRs 0202, 0304, 0305, 0306, `.docs/integration-plan.md` §2 and §6.

---

## 2. Scale-out: what we ran with more replicas, and what we did not

```bash
docker compose up -d --wait --scale worker=3 --scale analytics=2
```

With a `--local-llm` `.env`, `--wait` exits 1 once `ollama-pull` finishes; add `worker analytics` to the command ([`infra/README.md`](../infra/README.md#scale-out)).

| Service | Scales? | Evidence |
|---|---|---|
| `worker` (scraper) | **yes** | ran with 3; 17 scans, 223 documents; queue, locks and per-domain limits are in Redis |
| `analytics` | **yes** | ran with 2; 223 documents split 111 / 112, no overlap, 0 duplicate findings; a replica killed mid-batch lost nothing (its pending entries were claimed after 60 s) |
| `scheduler` | no (one by design) | started twice by mistake it is harmless: one job id per source and slot (code) |
| `api`, `web` | no | `api` ran with 2: the gateway sent all requests to one replica; balancing needs dynamic upstreams and Socket.IO stickiness |
| `gateway` | no | holds the host ports: a second replica fails to start |
| `postgres`, `redis`, `minio`, `ollama`, `renderer` | no | single node, no clustering configured; never `--scale` the data stores, a second replica shares the volume (`renderer` and `ollama` are optional) |

**Measured:** 892 queued documents drained in **21-24 s with one analytics replica and 9-10 s with two** (about 2.3×; rules-only, 12-CPU machine, documents already seen, so it says nothing about the LLM path). More scraper workers do not make one site faster: a domain is still fetched at most every 5 s, wherever it runs.

**Notes:** What to show live: `docker compose ps worker analytics` for the replicas, then the consumer list of `iw:documents` (command in `infra/README.md`, "Scale-out") and the per-replica document counts. Be ready for three questions. "Why not scale the API?": we ran it, found the gateway does not balance and a session would need to stick to one replica, and kept the claim to what we can show. "Is analytics safe with two replicas?": yes for results (no duplicate or lost finding in our runs); two near-identical documents handled in the same instant by different replicas can each open a duplicate-group, so one alert may appear twice. "Does the LLM scale?": no, each replica adds its own calls to the hosted model (which answered 503 under load in the #78 run), and the local Ollama is one instance. Resource cost of the scaled stack: the compose limits add 5 CPUs and 3.3 GB for `worker=3 analytics=2`, on top of the base stack (also in issue #75). Sources: `openspec/changes/archive/2026-11-22-architecture-scale-out/evidence.md`, `infra/README.md` "Scale-out", `infra/tests/smoke.sh scale`, `scraper/src/iw_scraper/scheduler.py:68`, `analytics/src/investwatch_analytics/neardup.py`.

**Not claimed:** scaling beyond one host, autoscaling, a clustered Postgres, Redis or MinIO, API replicas, any throughput number for the LLM path or for real scraping.
