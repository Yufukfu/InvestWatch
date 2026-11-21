## 1. Registry precedence

- [x] 1.1 Test: on a firm's domain the domain firm beats another firm's name; equal name hits go to the earliest quote
- [x] 1.2 `Registry.match` ranks domain-hosted firm first, then confidence, position, quote length
- [x] 1.3 Mutation check — mutations: 7 tried, 7 caught

## 2. CLI batch

- [x] 2.1 Test: one invalid document is skipped and the rest are analyzed; all invalid exits 2; the log carries no input values
- [x] 2.2 Per-item validation in `cli.main`, errors logged as `loc` and `type` only
- [x] 2.3 Mutation check — mutations: 7 tried, 7 caught

## 3. Rules and summary

- [ ] 3.1 Test: negated R2 label fails, mid-text label is `uncertain`; R3 accepts `nie jest wykluczona utrata`; summary skips `not_applicable` rules
- [ ] 3.2 R2 negation and prominence, R3 override patterns, summary wording
- [ ] 3.3 Mutation check

## 4. Sentences and logging docs

- [ ] 4.1 Test: `ok.` before an uppercase word ends a sentence, before a digit it does not; `2024 r.` does not
- [ ] 4.2 Split `_ABBREV` into always / before-digit lists; `logging_setup` docstring and `analytics/CLAUDE.md` note on stderr
- [ ] 4.3 Mutation check

## 5. Closing

- [ ] 5.1 Apply iw-docs-update (follow-ups, STATUS row) and add the iw-ai-log row
- [ ] 5.2 Run iw-pr-review checks and fix real findings
