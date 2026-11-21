# 0209. Verifiable supply chain: open-source dependency scanning and secret isolation

- Status: accepted
- Date: 2026-11-21
- Deciders: agent-written; accepted by Kacper via PR #47

## Context

The challenge requirements ask for a verifiable supply chain (cybersecurity): mandatory scanning of `npm` and `pip` dependencies with "Snyk-type" tools to remove vulnerabilities, strict isolation of secrets in `.env` files, and checking a package on a dedicated website before installing it, or fixing it with `npm audit` / `npm audit fix`. The same task asks for an on-premise, open-source stack ([integration-plan.md](../integration-plan.md) §7, LLM note), so the tools must be open source and able to run without a vendor cloud.

What the repository already does (checked on `main` at 657e4a7):

- **Dependencies.** Every Python service pins exact versions (`==`) in `requirements.txt`, without hashes. `web/` installs with `npm ci` from `package-lock.json`. `.github/workflows/ci.yml` runs `pip-audit` for each Python service and the mock server, and `npm audit --audit-level=high` for each `*/package-lock.json`. The workflow is `workflow_dispatch` only, so it is not a merge gate. Results are logged by hand in [security-audit.md](../security-audit.md) (three rows, all clean). In compose, Redis, MinIO and Ollama are pinned by digest ([ADR 0306](0306-object-storage-image.md)), while Postgres and Caddy use moving tags. Of the Dockerfile bases, only `analytics/` and `contracts/mock-server/` pin a digest; `api/` (`python:3.13-slim`), `scraper/` (`python:3.12-slim-bookworm`) and `web/` (`node:22-alpine`, `nginx-unprivileged:1.29-alpine`) use moving tags. GitHub Actions are pinned by tag (`actions/checkout@v4`), not by commit SHA, and CI installs `pip-audit` unpinned (`pip install pip-audit pytest`).
- **Secrets.** `.gitignore` ignores `.env` and `.env.*` except `.env.example`. The hook `.claude/hooks/git-guard.js` denies a commit with a staged `.env` file. The CI job `no-debug-output` fails on a tracked `.env`. `scripts/init-env.sh` creates `.env` with `umask 077` and random passwords, and compose refuses to start with empty passwords (`.env.example`). Nothing scans for a secret hard-coded outside a `.env` file, for example a key pasted into Python, YAML or a test.
- `npm audit` sends the lockfile's package names and versions to the npm registry's advisory endpoint, and `pip-audit` by default queries the PyPI JSON API. Neither works offline, and both cover one ecosystem only.

## Options considered

### Dependency scanning (SCA)

1. **Snyk** (named in the requirement as the example). The CLI is open source, but scanning needs a Snyk account (`snyk auth`) and sends the dependency graph to Snyk's cloud. The Free plan allows 200 Open Source tests per month for private repositories ([snyk.io/plans](https://snyk.io/plans/)), and each manifest counts as one test ([docs.snyk.io: what counts as a test](https://docs.snyk.io/working-with-snyk/what-counts-as-a-test)). The repository has ten manifests (nine `requirements*.txt` and `web/package-lock.json`), so that is about 20 full scans a month. The proprietary SaaS backend does not meet the on-premise, open-source requirement.
2. **`npm audit` + `pip-audit` only (status quo).** Native, and both are already in CI. `npm audit fix` and `pip-audit --fix` give the fix path the requirement names. Each tool covers one ecosystem and needs network access to a public registry.
3. **OSV-Scanner** (Google, Apache-2.0, [github.com/google/osv-scanner](https://github.com/google/osv-scanner)). One binary reads `package-lock.json` and `requirements*.txt` across the whole repository against the open OSV.dev database, which aggregates GitHub, PyPA and npm advisories. With `--offline-vulnerabilities --download-offline-databases` it scans against a locally downloaded database. With `--offline` it sends no project data anywhere, which makes it work on-premise and air-gapped ([offline mode docs](https://google.github.io/osv-scanner/usage/offline-mode)). License checks (`--licenses`) need deps.dev and cannot run together with offline mode.
4. **Trivy** (Aqua, Apache-2.0). It covers lockfiles, container images and IaC. In March 2026 attackers used stolen credentials to publish a malicious Trivy v0.69.4 and to repoint almost every tag of `aquasecurity/trivy-action` and `setup-trivy` to an infostealer ([GHSA-69fq-xp46-6x23](https://github.com/aquasecurity/trivy/security/advisories/GHSA-69fq-xp46-6x23), [Aqua](https://www.aquasec.com/blog/trivy-supply-chain-attack-what-you-need-to-know/)). The tool is not ruled out, but the incident shows that a scanner is part of the supply chain too and must be pinned by digest or SHA.

### Hard-coded secrets

1. **Status quo:** `.gitignore`, the hook and the CI check stop `.env` files only.
2. **Gitleaks** (MIT, offline, a single binary or image). We ran it on this repository: `gitleaks git` over the full `origin/main` history (v8.28.0, about 3.7 MB, under 7 s). The commit count of that run (276) could not be reproduced: `origin/main` is 390 commits at bb770a0 (2026-11-21), and the rerun in this session was not possible (Gitleaks not available here), so the scan must be repeated on a named SHA before its numbers are cited. It found 2 findings, both `generic-api-key` in `contracts/mocks/generate_mocks.py` (lines 145 and 299, commit 0893acdc). Both are false positives: a mock record's `key="m2-…"` identifier, not a credential. So the tool needs a reviewed allowlist (`.gitleaks.toml`) before it can gate anything.
3. **TruffleHog** (AGPL-3.0). Its main feature is verifying a found credential by calling the provider's API. That sends data out, and it can be turned off with `--no-verification`, which leaves a detector comparable to Gitleaks. Not evaluated further: we did not run it here, and Gitleaks already gave a measured result with an MIT license.

### Checking a package before install

The requirement allows doing this on a website. [osv.dev](https://osv.dev) (known vulnerabilities) and [deps.dev](https://deps.dev) (advisories, license, OpenSSF Scorecard, dependents, release history) are open, free and need no account, and only the package name is sent. `npm view <pkg> time` shows release dates from the command line. For Python, the PyPI project page (`https://pypi.org/project/<pkg>/`) shows the maintainers, release history and source link; `pip index versions <pkg>` lists version numbers only.

## Decision

All tools are open source and run locally or in our own CI. No vendor account is needed.

1. **Two scanners per ecosystem.** We keep `npm audit --audit-level=high` and `pip-audit` per service, because they are native and give the fix path (`npm audit fix`, bumping the `==` pin, `pip-audit --fix`). We add **OSV-Scanner** as one repository-wide scan over every lockfile and requirements file. In CI and on-premise it runs offline against a downloaded OSV database. OSV-Scanner is the scan that is documented upstream to work with no internet access (offline mode; not verified here, see Consequences).
2. **Gate: no open finding at merge.** A finding blocks the PR until it is fixed or documented as a residual risk in the audit log (advisory id, severity, why it is not exploitable here or that no fix is released, a revisit date). `npm audit` is gated at `--audit-level=high`, so its moderate and low findings are only logged. `pip-audit` reports no severity and OSV-Scanner has no severity-threshold flag (v2.2.4 `scan source --help`), and both exit non-zero on any finding, so every finding they report is fixed or logged; the residual-risk row cites the CVSS score from OSV-Scanner's output. `npm audit fix --force` is never run blind, because it allows semver-major upgrades. Every scan before a merge to `main` gets one row in [security-audit.md](../security-audit.md).
3. **Secrets.** Secrets live only in the untracked root `.env` created by `scripts/init-env.sh`, plus the per-module `.env` files for local runs. The current layers stay. We add **Gitleaks** over the full history in CI and over the working tree before a commit, with a reviewed `.gitleaks.toml` allowlist that starts with the two mock-id false positives above. A real finding means rotating the secret, not only deleting it, because git history keeps the old value.
4. **Before adding a direct dependency**, the author checks it on osv.dev and deps.dev (known vulnerabilities, license, maintenance, typosquat look-alikes). The PR body names the check and its result.
5. **Pinning.** Every scanner and every GitHub Action used for the supply-chain checks is pinned by image digest or commit SHA, never by a moving tag. The March 2026 Trivy compromise worked through moving tags.

How to run all this: [supply-chain.md](../supply-chain.md).

## Consequences

- The jury can verify the claim: one runbook and one audit log. Gitleaks is shown to run on-premise with Docker and no account; OSV-Scanner offline mode is documented upstream and unverified here.
- Implementation is a follow-up PR (owner Kacper; it touches `.github/workflows/ci.yml` and adds `.gitleaks.toml`). Until it lands, Gitleaks is run by hand with the runbook commands and the result is logged. OSV-Scanner has not finished a run on this repository yet: on an 8 GB MacBook Air under Docker Desktop it stalled after loading the npm database and was killed, so its first verified run is the CI job, not a developer laptop. The OSV-Scanner part of decision 2 does not bind (no PR is checked against it) until that CI job exists and has run green once; until then it is a manual run ([supply-chain.md](../supply-chain.md) §2). The root `CLAUDE.md` rule "`pip-audit` / `npm audit` before merge" is unchanged by this ADR.
- CI stays `workflow_dispatch` during the hackathon, so the gate is a PR-ready criterion ([CODE_REVIEW.md](../../.claude/CODE_REVIEW.md)), not a required check. Making the jobs required checks is the post-hackathon step already noted in `ci.yml`.
- Gitleaks false positives cost a little upkeep: each allowlist entry must name the file and why it is not a secret.
- Out of scope, for a later ADR: scanning container images (Grype or Trivy, pinned), digest-pinning the Postgres and Caddy images and the moving-tag Dockerfile bases, pinning `pip-audit` in CI, `--require-hashes` for pip, and SBOM generation.
