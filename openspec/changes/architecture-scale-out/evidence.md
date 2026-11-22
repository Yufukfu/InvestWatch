# Evidence: scale-out runs (2026-11-22, `main` 082736c)

Machine: Docker Desktop, 12 CPUs, 8 GB for the VM, fresh volumes, project `iw-arch-scale`, hosted LLM off (analytics rules-only). Commands are in `tasks.md` group 1 and `infra/tests/smoke.sh` group `scale`.

| Run | Result |
|---|---|
| `up -d --build --wait --scale worker=3 --scale analytics=2` | all healthy, 53 s with warm image cache |
| one `POST /api/scans` for each of the 17 seeded sources | 17 × 202; all three `worker` replicas executed jobs; 223 documents (same as the #78 run) |
| analytics after that run | replica 1 handled 111 distinct documents, replica 2 handled 112, overlap 0; 70 findings, 0 duplicate `(document_id, module)` rows, 0 ERROR lines |
| 223 ids re-announced four times, one analytics replica killed one second later | 2 entries pending at the kill (one per consumer); after the 60 s claim idle time `XPENDING` = 0 and group lag 0; findings still 70, duplicates 0 |
| `--scale scheduler=2` | both run; one `_job_id` per source and slot (`scheduler.py:68`), so a slot is enqueued once. Not run across a cron slot (6 h cron), so by code reading plus arq's job-id rule |
| `--scale gateway=2` | the second replica fails: `Bind for 127.0.0.1:18080 failed: port is already allocated` |
| `--scale api=2` through the gateway, 30 requests | all 30 reached one replica: Docker DNS returns both addresses but Caddy dials the name and Go takes the first, so nothing is balanced and no Socket.IO session is split. A second `api` replica would sit idle |
| 892 re-announced entries (223 ids × 4), time until group lag 0 and nothing pending, twice each | 1 analytics replica: 21 s, 24 s; 2 replicas: 9 s, 10 s (about 2.3×). Rules-only, documents already seen, `worker=3`; says nothing about the LLM path or about a real scrape |

Notes for the runbook:
- `XINFO CONSUMERS` keeps the names of killed or replaced replicas (4 listed after one restart with 2 running). Count consumers whose `idle` is small, or compare with the running containers, not the raw list.
- Near-duplicate grouping (`analytics/neardup.py`, `_observe`) reads then writes without a lock. Two replicas holding near-identical documents at the same moment can each start their own group, so one alert may be raised twice instead of merged. No finding is lost or duplicated. `HINCRBY` on `iw:stats:gate` and the LLM cache `SET`/`GET` are atomic or idempotent. Read from code, not forced in a run.
- Resource sum for `worker=3 analytics=2` from the compose limits: 3 × (1.0 CPU, 768 MB) + 2 × (1.0 CPU, 512 MB) = 5 CPUs, 3.3 GB for those two services, on top of the single-instance stack.
