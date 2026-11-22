# Tasks

## 1. Spec delta (docs-only, no logic: no test or mutation check)

- [x] 1.1 Checked the scraper container section of `.docs/security-audit.md` against `scraper/compose.yaml` and `scraper/Dockerfile` on `origin/main`: credentials, networks, `/health`, hardening, limits and image pin all match; nothing to fix
- [x] 1.2 Grepped `scraper/CLAUDE.md`, `scraper/README.md`, `.claude/skills`, `.docs` for an instruction to add a dated `pip-audit` row: none left
- [x] 1.3 MODIFIED delta for "Audited supply chain" in `specs/scraper-deployment/spec.md`; `openspec validate --all --strict` passes (`mutations: n/a, docs-only`)

## 2. Closing

- [x] 2.1 Apply the iw-docs-update skill (`docs-check: ok`; `.docs/status/scraper.md` row) and add the iw-ai-log row
- [x] 2.2 Run the iw-pr-review skill and fix real findings
