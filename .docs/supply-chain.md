# Supply chain: dependency scanning and secrets

Runbook for [ADR 0209](decisions/0209-supply-chain-scanning.md). This file says how; the ADR says why. Results go in the PR body, in a short **Security scans** section (commands, versions, result); [security-audit.md](security-audit.md) holds only service notes, the hand-in run and long-lived residual risks.

Every tool here is open source and runs locally with Docker or the language toolchain. None needs an account or sends source code anywhere.

## 1. Before adding a dependency

For every new **direct** dependency (`package.json`, `requirements*.txt`):

1. Look it up on [osv.dev](https://osv.dev) (known vulnerabilities for the exact version) and on [deps.dev](https://deps.dev) (license, OpenSSF Scorecard, maintainers, release history, dependents).
2. Check the name against typosquats: compare it with the project's real repository link, the download count and the publish date (`npm view <pkg> time repository`; for Python, the project page `https://pypi.org/project/<pkg>/` shows the maintainers, the release history and the source link).
3. Pin it: an exact `==` version in `requirements*.txt`, or a committed `package-lock.json` (install with `npm ci`).
4. Name the check in the PR body, for example: `deps.dev: MIT, Scorecard 7.1, no OSV advisories for 2.3.1`.

## 2. Scan before a merge to `main`

Run all three from the repository root. A finding blocks the PR until it is fixed or logged as a residual risk (ADR 0209, decision 2). `npm audit` is gated at `--audit-level=high`. `pip-audit` reports no severity and OSV-Scanner has no severity threshold, so every finding they report is fixed or logged; OSV-Scanner's table shows the CVSS score that the residual-risk row cites.

```bash
# Per-ecosystem, native (also in .github/workflows/ci.yml)
pip-audit -r <service>/requirements.txt -r <service>/requirements-dev.txt   # each Python service
(cd web && npm audit --audit-level=high)

# Repository-wide, offline against a local OSV database (on-premise mode): manifests only, not a recursive walk
docker run --rm -v "$PWD":/src:ro -v osv-db:/root/.cache/osv-scanner \
  ghcr.io/google/osv-scanner:v2.2.4 \
  scan source --offline --download-offline-databases \
  -L /src/web/package-lock.json \
  $(for f in */requirements*.txt contracts/mock-server/requirements*.txt; do printf -- '-L requirements.txt:/src/%s ' "$f"; done)
```

**Run it in CI, not on a developer laptop.** The CI offline job (section 5) completed on PR #100: it loaded the npm and PyPI databases and scanned 12 manifests in about 28 s. On a MacBook Air M1 (8 GB) under Docker Desktop, the same scan loaded `npm/all.zip` and then stalled until it was killed, leaving the cache empty (likely memory, unverified). On a machine with enough memory, check that `osv-db` is non-empty after the first run. Once it holds the database, an air-gapped host runs the same command without `--download-offline-databases`. The image is pinned by tag here for a manual run. CI pins it by digest (ADR 0209, decision 5).

## 3. Fixing a finding

| Ecosystem | Fix | Never |
|---|---|---|
| npm | `npm audit fix` (semver-compatible updates in the lockfile), then `npm ci && npm test`. For a transitive dependency with no compatible fix, use `overrides` in `package.json`. | `npm audit fix --force` without reading the diff, because it allows major upgrades |
| pip | Raise the `==` pin to the first fixed version that `pip-audit` reports (`pip-audit --fix` does it in place), then reinstall and run the service tests | Unpinning, or `>=` ranges |
| No fix released | Document the residual risk in the PR body: advisory id, severity, why it is not exploitable here, the revisit date. If it outlives the PR, also add it to `security-audit.md` | Silently ignoring it |

## 4. Secrets

- **Where secrets live.** Only in untracked `.env` files: the root `.env` that `scripts/init-env.sh` creates (`umask 077`, random passwords), plus a module's own `.env` for a local run. `.env.example` is tracked and keeps every secret empty. Config is env-only ([integration-plan.md](integration-plan.md) §7).
- **What already stops a leak.** `.gitignore` (`.env`, `.env.*`), the commit hook `.claude/hooks/git-guard.js` (denies a staged `.env`), and the CI job `no-debug-output` (fails on a tracked `.env`). Logs never print credentials (see the service notes in `security-audit.md`).
- **Hard-coded secrets** (a key pasted into code, YAML or a test) are caught by Gitleaks:

```bash
# Works in a plain clone and in a git worktree, whose .git is a file pointing at the main checkout.
# Mount the worktree and the shared git dir at fixed paths and tell git where they are. Mounting them
# at their host paths (-v "$PWD:$PWD") showed an empty directory under Docker Desktop on macOS.
GIT_COMMON=$(git rev-parse --path-format=absolute --git-common-dir)
GIT_SUB=$(git rev-parse --path-format=absolute --git-dir); GIT_SUB=${GIT_SUB#"$GIT_COMMON"}
GITLEAKS=zricethezav/gitleaks:v8.28.0@sha256:cdbb7c955abce02001a9f6c9f602fb195b7fadc1e812065883f695d1eeaba854
gitleaks() { docker run --rm -v "$PWD:/repo:ro" -v "$GIT_COMMON:/gitcommon:ro" -w /repo \
  -e GIT_DIR="/gitcommon$GIT_SUB" -e GIT_COMMON_DIR=/gitcommon -e GIT_WORK_TREE=/repo \
  -e GIT_CONFIG_COUNT=1 -e GIT_CONFIG_KEY_0=safe.directory -e GIT_CONFIG_VALUE_0='*' \
  "$GITLEAKS" git /repo --no-banner --redact "$@"; }
gitleaks --staged                  # staged changes, before a commit (tracked content only, never the untracked .env)
gitleaks --log-opts=origin/main    # full history of main
```

  Check the `N commits scanned` line: `0 commits` means git history was not readable (the worktree case above), and "no leaks found" is then false. `--redact` keeps the matched value out of the output. Never paste a finding's secret into a PR, an issue or a chat. Known false positives go in `.gitleaks.toml`, with the file and the reason. Put an entry on the rule that fires (`[[rules]] id = "<rule>"` plus `[[rules.allowlists]]`), never in a top-level `[[allowlists]]` with `paths`: in v8.28.0 that skips the whole file whatever `condition` says. Then check the entry with a scratch copy of the file plus a credential-shaped line, which must still be reported. The only entry today covers the two mock ids in `contracts/mocks/generate_mocks.py`.
- **A real secret was committed.** Rotate it first (new password in `.env`, then restart the stack), then remove it from the code. Deleting it alone is not enough: git history keeps the old value, and we never rewrite pushed history (root `CLAUDE.md`).

## 5. In CI

`.github/workflows/security.yml` runs on every pull request to `main` and by hand from the Actions tab. It is not a required check: a red job is fixed or logged as a residual risk in the PR body (section 3), it does not block the merge itself.

| Job | What it runs |
|---|---|
| Secrets (Gitleaks, full history) | every commit with `.gitleaks.toml`, values redacted. It fails when the log shows 0 commits scanned, because Gitleaks over an unreadable history says "no leaks found" and exits 0. |
| Dependencies (OSV-Scanner) | `scan source -r` over the checkout in online mode: only package names and versions go to osv.dev |
| Dependencies (OSV-Scanner, offline database) | by hand (start the workflow with `offline` ticked) and on every PR that changes `security.yml`, so a pin bump is proven before the merge. It downloads the databases first, the on-premise mode of ADR 0209 |
| Python dependencies (pip-audit) | every `requirements*.txt`, on Python 3.12 or 3.13 like the images. It fails if a requirements file is in a directory the matrix does not list |
| Node dependencies (npm audit) | every tracked `package-lock.json`, failing at high |

Every action is pinned by commit SHA, both images by digest and `pip-audit` by `==`. The test `.github/tests/workflow-pins.test.mjs` fails on anything unpinned in that file. To bump a tool, read the new SHA (`gh api repos/<owner>/<action>/git/ref/tags/<tag>`) or digest (`docker buildx imagetools inspect <image>:<tag>`) and change it in a PR.

## 6. Status

| Control | State |
|---|---|
| `pip-audit`, `npm audit` in CI | in `.github/workflows/ci.yml`, but manual `workflow_dispatch` only: not a required check and not a merge gate yet (ADR 0209, Consequences) |
| `.env` isolation (gitignore, hook, CI) | in place |
| OSV-Scanner | on every PR in `security.yml` (online); offline database by hand and on PRs that change `security.yml` (section 5) |
| Gitleaks + `.gitleaks.toml` | on every PR in `security.yml`, full history |
| `pip-audit`, `npm audit` on every PR | in `security.yml` (`pip-audit==2.10.1`) |
| Actions pinned by SHA, scanner images by digest | `security.yml`, enforced by `.github/tests/workflow-pins.test.mjs` |
| `ci.yml` actions by SHA, Postgres and Caddy images and the moving-tag Dockerfile bases (`api`, `scraper`, `web`) pinned by digest | follow-up |
