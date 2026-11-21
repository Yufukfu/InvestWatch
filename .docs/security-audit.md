# Dependency audits

`pip-audit` / `npm audit` results before a merge to `main` ([integration-plan.md](integration-plan.md) §7). Newest first; one row per run.

| Date | Module | Command | Result |
|---|---|---|---|
| 2026-11-21 | api (`api-db-schema`) | `pip-audit -r api/requirements.txt -r api/requirements-dev.txt` (pip-audit 2.10.1) | No known vulnerabilities found |
