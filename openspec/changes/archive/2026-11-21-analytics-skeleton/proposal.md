# Proposal

## Why

Integration #1 (Sat 17:00) needs analytics to turn a `ScrapedDocument` into schema-valid `Finding`s. `analytics/` holds only a README and a `CLAUDE.md` today. This change builds the infrastructure-free core of the service (`.docs/analytics-plan.md` §12.3, steps 1-6). The Redis worker, Postgres storage and events can then be added as a thin I/O layer on top.

## What Changes

- Add a self-contained Python package `analytics/` (`investwatch_analytics`) with env-only config, its own `pyproject.toml` and pytest suite, laid out as in `.docs/analytics-plan.md` §12.1-12.2.
- Add Pydantic models: a lenient input `ScrapedDocument` (unknown fields ignored) and a strict output `Finding` matching contract v1.
- Add preprocessing: Unicode NFKC normalization, whitespace cleanup, sentence split, sha256 content hash and a pl/en language guess.
- Add a KNF firm registry loaded from the CSV named by `REGISTRY_CSV`. It matches firms by name, alias, page domain and fuzzy name. A fictional seed `analytics/registry/seed.csv` holds the three mock firms, reusing their mock `registry_id`s.
- Add a rule engine with all 18 UKNF rules described in `m2_rules.yaml` (each has an `implemented` flag). Rules-only implementations are R1 (firm identification), R2 (ad labeling) and R3 (risk information next to return claims).
- Add a router (`firm_own` → M2; `third_party` / `unknown` → skipped and logged for now), an M2 module that builds the Finding (Polish title and summary, raw `score`), and a pure `analyze(document) -> list[Finding]` pipeline.
- Add a CLI: `python -m investwatch_analytics.cli <file.json>` analyzes a document, or a list of them, and prints findings as JSON with no infrastructure.
- Out of scope, each in a later change: the Redis Stream worker, Postgres storage, `iw:events` publishing and `finding.high_risk` thresholds (plan §12.3 steps 7-8, next change `analytics-worker`); the Dockerfile (step 9); rules R4-R18; modules M1 and M3; the LLM layer (`model.llm` is always `null` here); the real KNF page loader; the gold set and `eval/run.py`.
- Owner: module C (`analytics/`).
- Contracts: reads `ScrapedDocument` v1 and produces `Finding` v1 (`.docs/integration-plan.md` §3, §4). Changes no contract, REST route or event. Output is checked with `contracts/validate.py`.

## Capabilities

### New Capabilities
- `document-analysis`: turn one `ScrapedDocument` into zero or more contract-valid `Finding`s. Covers preprocessing, firm-registry matching, routing to modules and M2 finding assembly with scoring.
- `m2-compliance-rules`: the UKNF rule catalogue and the rules-only checks R1, R2 and R3, each yielding a `RuleResult` with an exact-quote evidence.

### Modified Capabilities

## Impact

- New code under `analytics/` only: `pyproject.toml`, `requirements.txt`, `requirements-dev.txt`, `.env.example`, `src/investwatch_analytics/`, `registry/seed.csv`, `tests/`.
- Dependencies: `pydantic`, `pyyaml`, `rapidfuzz`; dev: `pytest`, `jsonschema` (for contract tests). All pinned and scanned with `pip-audit` before merge.
- Docs: `analytics/README.md`, `analytics/CLAUDE.md` if needed, the analytics row of `.docs/STATUS.md`, an AI log row.
