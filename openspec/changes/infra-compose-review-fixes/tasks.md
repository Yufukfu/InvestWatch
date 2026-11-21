# Tasks

## 1. Secret bootstrap (`init-env.sh`, `.env.example`)

- [x] 1.1 Failing tests: re-running on an existing file exits 0 and keeps it; the LLM slots are present and empty after a run; without `openssl` on the PATH the run exits non-zero naming `openssl` and creates no file
- [x] 1.2 `init-env.sh`: existing file gives a message and exit 0; `value=$(gen) || value=` so the length check prints the message; `.env.example` gets empty `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`
- [x] 1.3 Mutation check (exit 1 on an existing file again; drop the `|| value=` fallback; let the fill pattern match `LLM_API_KEY`); mutations: 3 tried, 3 caught. The `openssl` test first passed vacuously on Git Bash (a `C:/...` PATH entry splits at the colon); it now converts the stub directory with `cygpath -u`

## 2. Smoke checks that can fail, portability

- [x] 2.1 Failing tests: `only_gateway_published` requires the gateway to publish a port; `anonymous_denied` sets the bucket public with root, reruns `minio-init`, then expects 403
- [x] 2.2 Replace every `sed -i` with a portable helper and `timeout` with a fallback that works without it; no behaviour change on Linux or Git Bash
- [x] 2.3 Mutation check (remove `mc anonymous set none` from `infra/minio/init.sh`; drop the gateway's `ports:`); mutations: 3 tried, 3 caught (no `anonymous set none`, gateway without `ports:`, `sedi` that never moves its temp file). Both strengthened checks passed on the real infra first, so the red proof is these mutants

## 3. Docs and ADRs

- [ ] 3.1 `infra/README.md`: smoke is not run in CI (no docker step in `.github/workflows/ci.yml`); the scraper trims `iw:documents` with `XADD ... MAXLEN ~ N`, because Redis is `noeviction`
- [ ] 3.2 Root `README.md`: "Licences of third-party services" (Postgres, Caddy, Redis 8 AGPLv3 option, MinIO via Chainguard AGPLv3, Ollama), one line and a link each
- [ ] 3.3 ADR 0202 lines 25 and 32 to the project-scoped `data`, `edge`, `egress` plus a "partly superseded by ADR 0306 (network names)" note; the matching line in ADR 0306; ADR 0306 evidence (SBOM licence, source repo, Valkey tags probed, AGPL Redis chosen deliberately)
- [ ] 3.4 `.docs/STATUS.md`: the Sat 14:30 milestone row and Damian's row; follow-ups row on why Postgres keeps its capabilities
- [ ] 3.5 Mutation check: mutations: n/a, docs-only group; `docs-check` passes

## 4. Closing

- [ ] 4.1 Apply the iw-docs-update skill (docs above, Damian's `.docs/STATUS.md` row, ADRs) and add the iw-ai-log row; `docker compose up` on an isolated project with `api-migrate` exiting 0, output kept for the PR body
- [ ] 4.2 Run the iw-pr-review skill and fix real findings
