# analytics

Analytics service: preprocessing, KNF firm registry, UKNF rule engine, modules M1–M3, LLM integration.

- **Owner:** Damian
- **Status:** core pipeline implemented (change `analytics-skeleton`): M2 for firm pages with rules-only R1–R3. No worker, storage, events, LLM, M1 or M3 yet. The worker is the next change, `analytics-worker`.

## Run locally (no infrastructure)

Python 3.12+.

```bash
cd analytics
python -m venv .venv && .venv/Scripts/python -m pip install -r requirements-dev.txt -e .   # Linux/macOS: .venv/bin/python
.venv/Scripts/python -m investwatch_analytics.cli ../contracts/mocks/documents.json > findings.json
.venv/Scripts/python ../contracts/validate.py finding findings.json
```

The CLI reads one `ScrapedDocument` or a list of them and writes `Finding`s as a JSON list to stdout. JSON logs go to stderr. An invalid document, or one whose analysis fails, is logged and skipped. Exit codes: 0 ok; 1 at least one document failed analysis (the others' findings are still written); 2 bad input, bad configuration, or no valid document (nothing on stdout).

## Tests

```bash
CONTRACTS_DIR=../contracts .venv/Scripts/python -m pytest -q
```

Without `CONTRACTS_DIR`, the contract tests are skipped, not failed.

## Configuration (env)

| Variable | Default | Meaning |
|---|---|---|
| `REGISTRY_CSV` | `registry/seed.csv` (fictional firms; only found from a source checkout or `pip install -e`, so set it in images) | KNF firm registry, format in [`registry/README.md`](registry/README.md) |
| `LOG_LEVEL` | `INFO` | log level |
| `CONTRACTS_DIR` | unset | tests only: path to `contracts/` |

## Where things are

- `src/investwatch_analytics/pipeline.py`: `analyze(doc, *, registry, catalogue, now)` → findings. Pure, no I/O.
- `src/investwatch_analytics/rules/m2_rules.yaml`: all 18 UKNF rules (name, severity, legal basis, dictionaries). Only entries with `implemented: true` run.
- `src/investwatch_analytics/rules/m2.py`: R1 firm identification, R2 ad labeling, R3 risk information next to return claims.
- Spec: [`openspec/specs/document-analysis/`](../openspec/specs/document-analysis/spec.md) and [`openspec/specs/m2-compliance-rules/`](../openspec/specs/m2-compliance-rules/spec.md); design and review follow-ups: [`openspec/changes/archive/2026-11-21-analytics-skeleton/`](../openspec/changes/archive/2026-11-21-analytics-skeleton/); plan: [`.docs/analytics-plan.md`](../.docs/analytics-plan.md).
