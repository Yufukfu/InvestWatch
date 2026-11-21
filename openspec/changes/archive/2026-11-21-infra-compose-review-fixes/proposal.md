## Why

Kacper's two reviews of PR #18 (`infra-compose`) asked for changes. Items 1 and 3 (merge conflicts; `api/compose.yaml` on the project-scoped network) are already settled by the merges of `main`.

Still blocking:
- `.docs/STATUS.md` is stale.
- Accepted ADR 0202 contradicts the new network names.
- The README has no licence note, although ADR 0306 promises one.

The minor items are concrete defects worth fixing before hand-in:
- two smoke checks cannot fail;
- the smoke test does not run on macOS;
- `init-env.sh` fails a repeated Quick Start run;
- there is no slot for the hosted LLM variables;
- Redis stream trimming is undocumented.

## What Changes

- **`scripts/init-env.sh`:**
  - An existing `.env` is left untouched, with a message and exit 0. It used to exit 1.
  - With `openssl` missing, it prints its helpful message instead of dying under `set -e`.
  - `LLM_API_KEY` is never auto-filled.
- **`.env.example`:** empty `LLM_BASE_URL`, `LLM_MODEL` and `LLM_API_KEY` lines for the hosted default of ADR 0304.
- **`infra/tests/smoke.sh`:**
  - Portable to macOS: no `sed -i`, and no `timeout` where it is missing.
  - `only_gateway_published` fails when the gateway publishes nothing.
  - `anonymous_denied` also proves that `minio-init` closes a bucket someone made public.
- **Docs and ADRs:**
  - `infra/README.md`: smoke is not run in CI; the scraper trims `iw:documents` with `XADD ... MAXLEN ~ N`.
  - Root `README.md`: a "Licences of third-party services" section.
  - ADR 0202 (Kacper asked for it): lines 25 and 32 use the project-scoped `data`, `edge` and `egress`, with a "partly superseded by ADR 0306" note, and a matching line in ADR 0306.
  - ADR 0306 evidence: the SBOM licence of the MinIO image, its source repository, and the deliberate choice of AGPL Redis over Valkey.
  - `.docs/STATUS.md`: the Sat 14:30 milestone row and Damian's row.
  - Follow-ups: why Postgres keeps its capabilities.
- **Out of scope:** pinning Postgres and Caddy by digest, and Postgres hardening (follow-ups).
- **Owner:** Damian. `infra/`, `scripts/init-env.sh` and ADR 0202 are Kacper's, and he requested these edits.
- **Contracts:** none touched. No REST route or event changes.

## Capabilities

### New Capabilities
- none

### Modified Capabilities
- `shared-infrastructure`:
  - `init-env.sh` is idempotent (exit 0 on an existing `.env`) and reports a missing `openssl`.
  - `.env.example` has empty hosted-LLM slots that are never auto-filled.
  - The default stack must show the gateway's published port.
  - `minio-init` re-closes a bucket that was made public.

## Impact

- **Files:** `scripts/init-env.sh`, `.env.example`, `infra/tests/smoke.sh`, `infra/README.md`, `README.md`, `.docs/decisions/0202-deployment-topology.md`, `.docs/decisions/0306-object-storage-image.md`, `.docs/STATUS.md`, `.docs/ai-workflow.md`.
- **Behaviour change:** `init-env.sh` now exits 0 on an existing `.env` instead of 1. The smoke test is the only caller, and it is updated.
