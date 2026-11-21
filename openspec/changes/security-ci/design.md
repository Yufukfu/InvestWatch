# Design

## Context

- `.github/workflows/ci.yml` stays `workflow_dispatch` only. Its `python` job runs `pip-audit` for each service, using a Python matrix (3.12 for `contracts analytics scraper`, 3.13 for `api`) because requirements resolve per interpreter. Its `node` job runs `npm audit --audit-level=high`.
- ADR 0209 and `.docs/supply-chain.md` already fix the tools and image versions:
  - Gitleaks v8.28.0 at `sha256:cdbb7c955abce02001a9f6c9f602fb195b7fadc1e812065883f695d1eeaba854`
  - OSV-Scanner v2.2.4 at `sha256:f7ba4be68bac8086b1f88fd598fdca1ca67239c79ad2c2b5c78e03a82e5187c4` (read from the local pull on 2026-11-21)
  - `pip-audit` 2.10.1, the version in every audit row
- Action SHAs, read with `gh api repos/<repo>/git/ref/tags/<tag>`:
  - `actions/checkout` v4.3.1 = `34e114876b0b11c390a56381ad16ebd13914f8d5`
  - `actions/setup-python` v5.6.0 = `a26af69be951a213d495a4c3e4e4022e16d87065`
  - `actions/setup-node` v4.4.0 = `49933ea5288caeca8642d1e84afbd3f7d6820020`
- Gitleaks on `ecb8124` finds exactly two `generic-api-key` hits, both in `contracts/mocks/generate_mocks.py` lines 145 and 299, on lines of the form `key="m2-…"`.
- Constraint: no heavy scan runs on the developer laptop (MacBook Air, 8 GB). OSV-Scanner is verified only in Actions. Gitleaks is light (5 s locally) and may be run locally to check the allowlist.

## Goals / Non-Goals

**Goals:**
- One separate workflow, so `ci.yml`'s behaviour does not change for teammates.
- No third-party action besides the official `actions/*`. The scanners run as digest-pinned images.

**Non-Goals:**
- No caching of the OSV offline database between runs (the offline job is manual and rare).
- No SARIF upload or code-scanning alerts. They need `security-events: write` and GitHub Advanced Security on private repositories.

## Decisions

1. **Scanners as `docker run` of digest-pinned images, not marketplace actions.**
   - `gitleaks/gitleaks-action` needs a license key for organization-owned repositories and pins its own binary version.
   - `google/osv-scanner-action` is a reusable workflow with nested pins.
   - A digest-pinned `docker run` is the same command as the runbook. It satisfies ADR 0209 decision 5 and the pin test checks it with one rule.
2. **OSV-Scanner online on pull requests, offline as a manual option.**
   - Online sends only package names and versions to osv.dev and needs no database download.
   - The offline job is the on-premise variant from ADR 0209. It runs only when the workflow is started by hand with the input `offline: true`.
   - Both scan the manifests found by `scan source -r .`. A new manifest is picked up without a workflow edit, and the runner has the memory the laptop did not.
3. **`pip-audit` mirrors `ci.yml`'s Python matrix.**
   - The interpreters are 3.12 for `contracts analytics scraper` and 3.13 for `api` and `contracts/mock-server`.
   - `pip-audit -r` resolves transitive dependencies in a temporary environment, which OSV-Scanner does not do for `requirements.txt`. That is the reason to keep both.
   - `pip install pip-audit==2.10.1`.
4. **The Gitleaks job scans the full history on every run** (`fetch-depth: 0`, `gitleaks git`), not only the PR's commits. It takes about 5 s on this repository. It also catches a secret that was rebased in, and the allowlist already covers the old hits.
5. **Allowlist in `.gitleaks.toml`:**
   - The file extends the default rules (`[extend] useDefault = true`) and has one allowlist entry with a `description`, on the `generic-api-key` rule (`[[rules]] id = "generic-api-key"` with `[[rules.allowlists]]`).
   - Not a top-level `[[allowlists]]`: in v8.28.0 a top-level entry with `paths` skips the whole file whatever `condition` says, which hid a credential-shaped line added to a scratch copy of the mock file. `targetRules` on a top-level entry did not apply to the extended default rule. Both were checked locally (tasks 2.1).
   - The entry combines `paths` (`contracts/mocks/generate_mocks.py`), `regexTarget = "line"` and a regex for `key="m<digit>-…"`, joined with `condition = "AND"`.
   - Alternative rejected: `.gitleaksignore` fingerprints. They are exact per commit and line, so they break when the mock file is regenerated, and they carry no reason field.
6. **Pin test: a dependency-free Node test, `.github/tests/workflow-pins.test.mjs`.** It reads `.github/workflows/security.yml` as text and asserts three things:
   - every `uses:` ends in `@<40 hex>`
   - every image passed to `docker run` contains `@sha256:<64 hex>`
   - every `pip install` of a scanner uses `==`

   It runs in `ci.yml`'s `Specs and hooks` step (one glob added) and locally in under a second. A YAML parser would be a new dependency for a text check.
7. **Workflow hygiene:**
   - `permissions: contents: read` and the `pull_request` trigger, never `pull_request_target`, so code from a fork never runs with secrets.
   - No secrets are used at all.
   - `concurrency` per ref with `cancel-in-progress`.
   - Job timeouts: 10 min for each scan, 20 min for the offline one.

## Risks / Trade-offs

- osv.dev, PyPI or the npm registry is down → the scan fails red on a PR. It is not a required check, so nobody is blocked; re-run it later.
- The pinned SHAs and digests go stale and miss fixes in the tools → bump them by hand in a PR, which the pin test keeps honest. Automated bumps (Dependabot or Renovate) are out of scope.
- The allowlist regex is too broad and hides a real secret in the mock file → it is limited to one path and the exact `key="m<digit>-` id shape. A real key in the same file on a differently shaped line still fails.
- The offline database is large and the job is slow → it is manual only, with its own 20-minute timeout.
- An existing vulnerability makes the first run red → expected. It is fixed or documented in that PR's body per ADR 0209 decision 2 before the hand-in run.

## Migration Plan

Merge, start the workflow once on `main` by hand, link that run in `.docs/security-audit.md` as the hand-in scan. Rollback: delete `security.yml`. Nothing else depends on it.
