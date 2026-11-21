## Why

Kacper's second review of PR #10 (head after the first review fixes) found 2 important defects and 5 nits. A bad catalogue parameter or one failing document crashes the CLI instead of a clean exit code; R2, R3 and the fuzzy match misjudge some realistic texts.

## What Changes

- Catalogue: `negation_before`, `prominent_sentences`, `footnote_markers` are validated at load; a non-mapping YAML root is a `CatalogueError`.
- CLI: an exception while analyzing one document is logged (document id, exception type) and that document is skipped; the others' findings are still written; exit 1 when any document failed.
- Registry: the "cannot read registry" error tells the operator to set `REGISTRY_CSV` (the default points into the source tree and is not packaged; follow-up #3 of `analytics-skeleton`).
- Registry: the fuzzy target is tokenized like the text, so hyphenated names match.
- R3: the denial exclusions use a precise loss stem (`strat…`, `straci…`, `utrat…`, not `strategia`), the `bez … ryzyko` denial needs the genitive `ryzyka`, and a risk word between a denial word and a loss word ends the denial (`bez opłat ryzyko utraty` stays a warning).
- R2: `tylko`, `jedynie`, `wyłącznie`, `only`, `just` between the negation and the label cancel it (`to nie tylko reklama`).

## Capabilities

### New Capabilities
- none

### Modified Capabilities
- `document-analysis`: CLI analysis failures, registry error hint, fuzzy tokenization.
- `m2-compliance-rules`: catalogue parameter validation, R2 `nie tylko`, R3 denial scope.

## Impact

- Owner: C (`analytics/`). No contract, REST route or event changes; output still validates against `finding.schema.json` v1.
- New CLI exit code 1 (some documents failed analysis); exits 0 and 2 unchanged.
