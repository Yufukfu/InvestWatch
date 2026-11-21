# Tasks

## 1. Package skeleton, config and models

- [x] 1.1 Failing test: a `Finding` built from the models validates against `contracts/schemas/finding.schema.json` (skipped without `CONTRACTS_DIR`), every mock document parses, an unknown field is ignored, missing `text` / bad `fetched_at` raise
- [x] 1.2 `analytics/pyproject.toml`, pinned `requirements.txt` / `requirements-dev.txt`, `.env.example` (`REGISTRY_CSV`, `LOG_LEVEL`, `CONTRACTS_DIR`), `config.py`, `models.py`, JSON logging setup; `pytest analytics` green
- [x] 1.3 Mutation check; `mutations: 6 tried, 6 caught` (one equivalent mutant removed with the dead code it hit)

## 2. Preprocessing

- [x] 2.1 Failing tests for the preprocessing scenarios (hash equality, `S.A.` split, pl/en guess, empty text)
- [x] 2.2 `preprocessing.py`; tests green
- [x] 2.3 Mutation check; `mutations: 11 tried, 11 caught` (two equivalent mutants removed with the redundant code they hit)

## 3. Firm registry

- [x] 3.1 Failing tests for the registry scenarios (name without legal form, domain, no match, missing/malformed CSV)
- [x] 3.2 `registry.py` and `analytics/registry/seed.csv` with the three fictional mock firms; tests green
- [x] 3.3 Mutation check; `mutations: 18 tried, 17 caught` (1 equivalent: `elif` -> `if` only adds a lower-confidence candidate for the same firm, which never wins; the short-name fuzzy guard was removed as unreachable at ratio >= 88)

## 4. Rule engine and R1-R3

- [x] 4.1 Failing tests for the catalogue, evidence and R1/R2/R3 scenarios
- [x] 4.2 `rules/engine.py`, `rules/m2_rules.yaml` (19 entries, R1-R3 implemented), `rules/m2.py`; tests green
- [x] 4.3 Mutation check; `mutations: 24 tried, 24 caught`

## 5. Router, M2 module and pipeline

- [x] 5.1 Failing tests for routing and M2 finding assembly (alfa landing, bank OK, unmatched firm, third-party skip, score formula)
- [x] 5.2 `modules/router.py`, `modules/m2.py`, `pipeline.py`; tests green
- [x] 5.3 Mutation check; `mutations: 14 tried, 14 caught`

## 6. CLI

- [x] 6.1 Failing test: the CLI on `contracts/mocks/documents.json` writes a JSON list of findings that passes `contracts/validate.py finding`
- [x] 6.2 `cli.py` (`python -m investwatch_analytics.cli <file>`, accepts an object or a list); tests green; `pip-audit -r analytics/requirements.txt` clean
- [x] 6.3 Mutation check; `mutations: 7 tried, 7 caught` (includes the `module` log-key fix found by the CLI test; `pip-audit`: no known vulnerabilities)

## 7. Closing

- [x] 7.1 Apply the iw-docs-update skill (`analytics/README.md` with how to run, analytics row of `.docs/STATUS.md`, `docs-check` clean) and add the iw-ai-log row
- [ ] 7.2 Run the iw-pr-review skill and fix real findings
