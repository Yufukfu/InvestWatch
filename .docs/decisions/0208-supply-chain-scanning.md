# 0208. Verifiable supply chain: open-source dependency scanning and secret isolation

- Status: accepted
- Date: 2026-11-21
- Deciders: agent-written; accepted by Kacper via PR #<n>

## Context

The challenge requirements ask for a verifiable supply chain (cybersecurity): mandatory scanning of `npm` and `pip` dependencies with "Snyk-type" tools to remove vulnerabilities, strict isolation of secrets in `.env` files, and checking a package on a dedicated website before installing it, or fixing it with `npm audit` / `npm audit fix`. The same task asks for an on-premise, open-source stack ([integration-plan.md](../integration-plan.md) §7, LLM note), so the tools must be open source and able to run without a vendor cloud.

What the repository already does (checked on `main` at 657e4a7):

- **Dependencies.** Every Python service pins exact versions (`==`) in `requirements.txt`, without hashes. `web/` installs with `npm ci` from `package-lock.json`. `.github/workflows/ci.yml` runs `pip-audit` for each Python service and the mock server, and `npm audit --audit-level=high` for each `*/package-lock.json`. The workflow is `workflow_dispatch` only, so it is not a merge gate. Results are logged by hand in [security-audit.md](../security-audit.md) (three rows, all clean). Third-party base and service images in compose are pinned by digest where [ADR 0306](0306-object-storage-image.md) did it (Redis, MinIO, Ollama); Postgres and Caddy use moving tags. GitHub Actions are pinned by tag (`actions/checkout@v4`), not by commit SHA.
- **Secrets.** `.gitignore` ignores `.env` and `.env.*` except `.env.example`. The hook `.claude/hooks/git-guard.js` denies a commit with a staged `.env` file. The CI job `no-debug-output` fails on a tracked `.env`. `scripts/init-env.sh` creates `.env` with `umask 077` and random passwords, and compose refuses to start with empty passwords (`.env.example`). Nothing scans for a secret hard-coded outside a `.env` file, for example a key pasted into Python, YAML or a test.
- `npm audit` sends the lockfile's package names and versions to the npm registry's advisory endpoint, and `pip-audit` by default queries the PyPI JSON API. Neither works offline, and both cover one ecosystem only.

## Options considered

### Dependency scanning (SCA)

1. **Snyk** (named in the requirement as the example). The CLI is open source, but scanning needs a Snyk account (`snyk auth`) and sends the dependency graph to Snyk's cloud. The Free plan allows 200 Open Source tests per month for private repositories, and each manifest counts as one test ([snyk.io/blog/requiring-authentication](https://snyk.io/blog/requiring-authentication/), [docs.snyk.io: what counts as a test](https://docs.snyk.io/working-with-snyk/what-counts-as-a-test)). With six manifests, that is about 33 full scans a month. The proprietary SaaS backend does not meet the on-premise, open-source requirement.
2. **`npm audit` + `pip-audit` only (status quo).** Native, and both are already in CI. `npm audit fix` and `pip-audit --fix` give the fix path the requirement names. Each tool covers one ecosystem and needs network access to a public registry.
3. **OSV-Scanner** (Google, Apache-2.0, [github.com/google/osv-scanner](https://github.com/google/osv-scanner)). One binary reads `package-lock.json` and `requirements*.txt` across the whole repository against the open OSV.dev database, which aggregates GitHub, PyPA and npm advisories. With `--offline-vulnerabilities --download-offline-databases` it scans against a locally downloaded database. With `--offline` it sends no project data anywhere, which makes it work on-premise and air-gapped ([offline mode docs](https://google.github.io/osv-scanner/usage/offline-mode)). License checks (`--licenses`) need deps.dev and cannot run together with offline mode.
4. **Trivy** (Aqua, Apache-2.0). It covers lockfiles, container images and IaC. In March 2026 attackers used stolen credentials to publish a malicious Trivy v0.69.4 and to repoint almost every tag of `aquasecurity/trivy-action` and `setup-trivy` to an infostealer ([GHSA-69fq-xp46-6x23](https://github.com/aquasecurity/trivy/security/advisories/GHSA-69fq-xp46-6x23), [Aqua](https://www.aquasec.com/blog/trivy-supply-chain-attack-what-you-need-to-know/)). The tool is not ruled out, but the incident shows that a scanner is part of the supply chain too and must be pinned by digest or SHA.

### Hard-coded secrets

1. **Status quo:** `.gitignore`, the hook and the CI check stop `.env` files only.
2. **Gitleaks** (MIT, offline, a single binary or image). We ran it on this repository: `gitleaks git` over the full `origin/main` history (v8.28.0, 276 commits, about 3.7 MB, under 7 s). It found 2 findings, both `generic-api-key` in `contracts/mocks/generate_mocks.py` (lines 145 and 299, commit 0893acdc). Both are false positives: a mock record's `key="m2-…"` identifier, not a credential. So the tool needs a reviewed allowlist (`.gitleaks.toml`) before it can gate anything.
3. **TruffleHog** (AGPL-3.0). It verifies live credentials by calling the provider, which sends data out and does not fit on-premise use.

### Checking a package before install

The requirement allows doing this on a website. [osv.dev](https://osv.dev) (known vulnerabilities) and [deps.dev](https://deps.dev) (advisories, license, OpenSSF Scorecard, dependents, release history) are open, free and need no account, and only the package name is sent. `npm view <pkg>` and `pip index versions <pkg>` show the publisher and release dates from the command line.

## Decision

All tools are open source and run locally or in our own CI. No vendor account is needed.

1. **Two scanners per ecosystem.** We keep `npm audit --audit-level=high` and `pip-audit` per service, because they are native and give the fix path (`npm audit fix`, bumping the `==` pin, `pip-audit --fix`). We add **OSV-Scanner** as one repository-wide scan over every lockfile and requirements file. In CI and on-premise it runs offline against a downloaded OSV database. Two databases (registry advisories and OSV) catch more than one, and OSV-Scanner is the scan that still works with no internet access.
2. **Gate: no high or critical vulnerability at merge.** A high or critical finding blocks the PR until it is fixed or documented as a residual risk in the audit log (not exploitable here, no fix released, with a revisit date). Moderate and low findings are logged. `npm audit fix --force` is never run blind, because it allows semver-major upgrades. Every scan before a merge to `main` gets one row in [security-audit.md](../security-audit.md).
3. **Secrets.** Secrets live only in the untracked root `.env` created by `scripts/init-env.sh`, plus the per-module `.env` files for local runs. The current layers stay. We add **Gitleaks** over the full history in CI and over the working tree before a commit, with a reviewed `.gitleaks.toml` allowlist that starts with the two mock-id false positives above. A real finding means rotating the secret, not only deleting it, because git history keeps the old value.
4. **Before adding a direct dependency**, the author checks it on osv.dev and deps.dev (known vulnerabilities, license, maintenance, typosquat look-alikes). The PR body names the check and its result.
5. **Pinning.** Every scanner and every GitHub Action used for the supply-chain checks is pinned by image digest or commit SHA, never by a moving tag. The March 2026 Trivy compromise worked through moving tags.

How to run all this: [supply-chain.md](../supply-chain.md).

## Consequences

- The jury can verify the claim: one runbook, one audit log, and scans that a teammate or the jury can run on-premise with Docker and no account.
- Implementation is a follow-up PR (owner Kacper; it touches `.github/workflows/ci.yml` and adds `.gitleaks.toml`). Until it lands, OSV-Scanner and Gitleaks are run by hand with the commands in the runbook, and the result is logged.
- CI stays `workflow_dispatch` during the hackathon, so the gate is a PR-ready criterion ([CODE_REVIEW.md](../../.claude/CODE_REVIEW.md)), not a required check. Making the jobs required checks is the post-hackathon step already noted in `ci.yml`.
- Gitleaks false positives cost a little upkeep: each allowlist entry must name the file and why it is not a secret.
- Out of scope, for a later ADR: scanning container images (Grype or Trivy, pinned), digest-pinning the Postgres and Caddy images, `--require-hashes` for pip, and SBOM generation.
