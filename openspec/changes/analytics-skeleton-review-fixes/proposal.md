## Why

Kacper's review of PR #10 (`analytics-skeleton`) found two important defects (a firm's own page judged against the wrong firm; one bad document in a CLI batch dropping every result) and six smaller ones in R2, R3, sentence splitting, logging and the summary. Fixing them before merge keeps the M2 results trustworthy for the worker and the demo.

## What Changes

- Registry: when the page host is a registered firm's domain, that firm wins over a name hit for another firm; ties between name hits go to the earliest, then the longest, quote (closes follow-up #10).
- CLI: documents are validated one by one; invalid ones are logged (`index`, `loc`, `type`, no input values) and skipped; exit 2 only when the input has documents and none is valid.
- R2: a negated label (`to nie jest reklama`, `not an ad`) does not count; a label only in the middle of the text (outside the first and last two sentences, not a hashtag) gives `uncertain` instead of `pass`.
- R3: `nie jest wykluczona utrata…`, `nie można wykluczyć straty`, `nie wykluczamy strat` and `nie gwarantujemy braku strat` count as warnings (override patterns; closes the rarer part of follow-up #19).
- Sentence splitting: `ok.`, `tel.`, `tys.`, `mln.`, `godz.`, `ust.`, `lit.`, `art.`, `pkt.`, `ww.`, `im.` end a sentence unless a digit follows; `<year> r.` never ends one.
- Summary: "Sprawdzono reguły …" lists only applicable rules; `not_applicable` ones are named separately (closes follow-up #16).
- `logging_setup` docstring and `analytics/CLAUDE.md` record that the CLI logs to stderr because stdout carries the findings.

## Capabilities

### New Capabilities
- none

### Modified Capabilities
- `document-analysis`: registry domain precedence and tie-break, sentence-split abbreviations, summary wording, CLI batch behaviour.
- `m2-compliance-rules`: R2 negation and prominence, R3 negated-exclusion warnings.

## Impact

- Owner: C (`analytics/`). Touches no contract, REST route or event. Output still validates against `finding.schema.json` v1.
- Out of scope: nothing else from the review; follow-ups #10, #16 and #19 are updated in the archived `follow-ups.md`.
