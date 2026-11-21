# Follow-ups

Out-of-scope findings from the per-group reviews (iw-commit-cycle step 8).

| # | Finding | Source | Disposition |
|---|---|---|---|
| 1 | `edge` is a normal bridge, so every routed service (gateway, web, later api) has outbound internet. Making it internal needs a separate publishing network for the gateway only. | group 5 review | `new-item`: Kacper's gateway topology (ADR 0202); spec and design now state the real rule |
| 2 | On Linux Docker before 28.0, ports published on `127.0.0.1` can be reached from the LAN by routing to the container IP; the dev-ports override relies on loopback binding. | group 5 review | `docs`: dev ports are for laptops on Docker 28+ (verified on 28.5.1) |
| 3 | `s3:AbortMultipartUpload` / `ListMultipartUploadParts` may be needed if a client uploads large media in parts. | group 4 review | `new-item`: add to the `iw-bucket-rw` policy when the scraper stores media |
| 4 | Smoke helpers pass throwaway MinIO test credentials on the host's `docker run` argv (`-e MC_HOST_t=...`). | group 4 review | `wont-fix`: test-only, random per run, removed with the project |
| 5 | `ollama` and `ollama-pull` run as root (models under `/root/.ollama`); a non-root user needs a volume path the user owns. | whole-branch security review | `new-item`: after the hackathon; both have read-only rootfs, tmpfs, `cap_drop: [ALL]`, and serving `ollama` has no internet |
| 6 | Smoke proves the module starts after `minio-init` finishes; the `postgres`/`redis` `service_healthy` ordering is not separately proven (they become healthy well before `minio-init` ends). | whole-branch review | `docs`: stated in tasks 7.3 |
| 7 | ADR 0202 still describes the fixed `iw-edge`/`iw-data` names and the old joining snippet. ADRs are append-only. | whole-branch review | `new-item`: Kacper decides whether a short superseding ADR is needed; `infra/README.md` and `infra/CLAUDE.md` are current |
| 8 | `scraper/CLAUDE.md`, `.docs/analytics-plan.md` and `openspec/changes/scraper-v1/proposal.md` still say `docker-compose.yml`. | whole-branch review | `new-item`: owners' files (Adam; Damian's analytics sessions) |
| 9 | Redis has one `default` user with full rights for every module; per-module ACL users would be tighter. Postgres and Caddy images are not digest-pinned and Postgres has no `cap_drop` (pre-existing). | whole-branch security review | `new-item`: hardening after Integration #2 |
| 10 | No smoke check for `cap_drop`, `read_only`, `no-new-privileges`, `user: redis` or the `.env` file mode. | whole-branch security review | `new-item`: add a `docker inspect` hardening check |
