# Proposal

## Why

[ADR 0209](../../../.docs/decisions/0209-supply-chain-scanning.md) decided on a verifiable supply chain (dependency scanning and secret scanning, open source, no vendor account), but none of it runs automatically. `.github/workflows/ci.yml` is `workflow_dispatch` only, and Gitleaks and OSV-Scanner run nowhere. The OSV-Scanner run never finished on a developer laptop (8 GB), so its first verified run has to happen in CI. The hand-in is Sun 10:30, and the jury should see the scans running on PRs, not only a document.

## What Changes

- New workflow `.github/workflows/security.yml`, triggered on `pull_request` to `main` and on `workflow_dispatch`. It runs these jobs on GitHub-hosted runners:
  - **Gitleaks** over the full git history, with `--redact`.
  - **OSV-Scanner** (online, against osv.dev) over every lockfile and requirements file.
  - **`pip-audit`** per Python service and the mock server.
  - **`npm audit --audit-level=high`** for `web/`.
- A manual-only job (`workflow_dispatch` input) runs OSV-Scanner in offline mode with a downloaded database, the on-premise variant from ADR 0209.
- New `.gitleaks.toml`: the default rules plus a reviewed allowlist for the two known false positives (mock ids in `contracts/mocks/generate_mocks.py`), each with its reason.
- Every action is pinned by commit SHA, every image by digest, and `pip-audit` by version (ADR 0209 decision 5). A Node test, `.github/tests/workflow-pins.test.mjs`, fails on an unpinned `uses:`, an image without a digest, or an unpinned `pip-audit`. The CI job `Specs and hooks` runs it.
- The jobs are **not required checks**. A red scan shows on the PR but does not block a merge during the hackathon. Required checks in branch protection are the production step (ADR 0209 Consequences).
- After the merge, one `workflow_dispatch` run on `main` is linked in `.docs/security-audit.md` as the hand-in scan.
- `ci.yml` is not changed; its manual audit jobs stay as they are.

## Capabilities

### New Capabilities
- `supply-chain-scanning`: automatic dependency and secret scanning of the repository in CI. It covers what runs, when it runs, what fails it, how false positives are allowed, and how the tools are pinned.

### Modified Capabilities
- none

## Impact

- **Owner:** Kacper (`chore/`, repository tooling). It touches no service code, no contract, no REST route and no event.
- **New files:**
  - `.github/workflows/security.yml`, `.gitleaks.toml`
  - `.github/tests/workflow-pins.test.mjs`. `.github/tests/` is a new directory, added by Kacper, who owns the layout.
- **Edited files:**
  - `.github/workflows/ci.yml`: one glob added to the `Specs and hooks` test step, no other change.
  - Docs: `.docs/supply-chain.md` (status table, CI section), `.docs/security-audit.md` (the hand-in run), `.docs/status/dashboard.md`, an AI-log row.
- **Teammates:** every PR to `main` gets a "security" check run, which takes a few minutes of GitHub Actions time.
  - It sends package names and versions to osv.dev, PyPI and the npm registry. No source code leaves the repository.
  - A red check is information, not a block.
- **Out of scope:**
  - required checks or branch protection
  - container image scanning, SBOMs, `--require-hashes`
  - digest-pinning the existing compose images and Dockerfile bases
  - changing `ci.yml` triggers
  - the `scraper-deployment` spec row (issue #66)
