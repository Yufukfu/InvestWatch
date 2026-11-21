# Dependency audits

`pip-audit` / `npm audit` results before a merge to `main` ([integration-plan.md](integration-plan.md) §7). Newest first; one row per run.

| Date | Module | Command | Result |
|---|---|---|---|
| 2026-11-21 | api (`api-v1`) | `pip-audit -r api/requirements.txt -r api/requirements-dev.txt` (pip-audit 2.10.1; FastAPI 0.165.0, python-socketio 5.18.1, redis 8.1.0, minio 7.2.20) | No known vulnerabilities found |
| 2026-11-21 | api (`api-db-schema`) | `pip-audit -r api/requirements.txt -r api/requirements-dev.txt` (pip-audit 2.10.1) | No known vulnerabilities found |
