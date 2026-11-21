# Supply chain: dependency scanning and secrets

Runbook for [ADR 0208](decisions/0208-supply-chain-scanning.md). This file says how; the ADR says why. Results go to [security-audit.md](security-audit.md), one row per run.

Every tool here is open source and runs locally with Docker or the language toolchain. None needs an account or sends source code anywhere.

## 1. Before adding a dependency

For every new **direct** dependency (`package.json`, `requirements*.txt`):

1. Look it up on [osv.dev](https://osv.dev) (known vulnerabilities for the exact version) and on [deps.dev](https://deps.dev) (license, OpenSSF Scorecard, maintainers, release history, dependents).
2. Check the name against typosquats: compare it with the project's real repository link, the download count and the publish date (`npm view <pkg> time repository`, `pip index versions <pkg>`).
3. Pin it: an exact `==` version in `requirements*.txt`, or a committed `package-lock.json` (install with `npm ci`).
4. Name the check in the PR body, for example: `deps.dev: MIT, Scorecard 7.1, no OSV advisories for 2.3.1`.

## 2. Scan before a merge to `main`

Run all three from the repository root. A **high or critical** finding blocks the PR (ADR 0208, decision 2).

```bash
# Per-ecosystem, native (also in .github/workflows/ci.yml)
pip-audit -r <service>/requirements.txt -r <service>/requirements-dev.txt   # each Python service
(cd web && npm audit --audit-level=high)

# Repository-wide, offline against a local OSV database (on-premise mode)
docker run --rm -v "$PWD":/src:ro -v osv-db:/root/.cache/osv-scanner \
  ghcr.io/google/osv-scanner:v2.2.4 \
  scan source --offline-vulnerabilities --download-offline-databases -r /src
```

Once `osv-db` holds the database, an air-gapped host runs the same command with `--offline` in place of the two offline flags. The image is pinned by tag here for a manual run. CI pins it by digest (ADR 0208, decision 5).

## 3. Fixing a finding

| Ecosystem | Fix | Never |
|---|---|---|
| npm | `npm audit fix` (semver-compatible updates in the lockfile), then `npm ci && npm test`. For a transitive dependency with no compatible fix, use `overrides` in `package.json`. | `npm audit fix --force` without reading the diff, because it allows major upgrades |
| pip | Raise the `==` pin to the first fixed version that `pip-audit` reports (`pip-audit --fix` does it in place), then reinstall and run the service tests | Unpinning, or `>=` ranges |
| No fix released | Record a residual risk row in `security-audit.md`: advisory id, why it is not exploitable here, the revisit date | Silently ignoring it |

## 4. Secrets

- **Where secrets live.** Only in untracked `.env` files: the root `.env` that `scripts/init-env.sh` creates (`umask 077`, random passwords), plus a module's own `.env` for a local run. `.env.example` is tracked and keeps every secret empty. Config is env-only ([integration-plan.md](integration-plan.md) §7).
- **What already stops a leak.** `.gitignore` (`.env`, `.env.*`), the commit hook `.claude/hooks/git-guard.js` (denies a staged `.env`), and the CI job `no-debug-output` (fails on a tracked `.env`). Logs never print credentials (see the service notes in `security-audit.md`).
- **Hard-coded secrets** (a key pasted into code, YAML or a test) are caught by Gitleaks:

```bash
# Working tree, before a commit
docker run --rm -v "$PWD":/repo:ro \
  zricethezav/gitleaks:v8.28.0@sha256:cdbb7c955abce02001a9f6c9f602fb195b7fadc1e812065883f695d1eeaba854 \
  dir /repo --no-banner --redact
# Full history (in a git worktree, also mount the main checkout's .git at the same path)
docker run --rm -v "$PWD":/repo:ro \
  zricethezav/gitleaks:v8.28.0@sha256:cdbb7c955abce02001a9f6c9f602fb195b7fadc1e812065883f695d1eeaba854 \
  git /repo --no-banner --redact
```

  `--redact` keeps the matched value out of the output. Never paste a finding's secret into a PR, an issue or a chat. Known false positives go in `.gitleaks.toml` (added with the CI follow-up), with the file and the reason. The first two are the mock ids in `contracts/mocks/generate_mocks.py`.
- **A real secret was committed.** Rotate it first (new password in `.env`, then restart the stack), then remove it from the code. Deleting it alone is not enough: git history keeps the old value, and we never rewrite pushed history (root `CLAUDE.md`).

## 5. Status

| Control | State |
|---|---|
| `pip-audit`, `npm audit` in CI | in `.github/workflows/ci.yml` (manual `workflow_dispatch`) |
| `.env` isolation (gitignore, hook, CI) | in place |
| OSV-Scanner (offline) | manual (section 2); CI job is the ADR 0208 follow-up |
| Gitleaks + `.gitleaks.toml` | manual (section 4); CI job is the ADR 0208 follow-up |
| Actions pinned by SHA, Postgres and Caddy images by digest | follow-up |
