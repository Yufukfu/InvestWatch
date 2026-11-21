## 1. Registry precedence

- [x] 1.1 Test: on a firm's domain the domain firm beats another firm's name; equal name hits go to the earliest quote
- [x] 1.2 `Registry.match` ranks domain-hosted firm first, then confidence, position, quote length
- [x] 1.3 Mutation check — mutations: 7 tried, 7 caught

## 2. CLI batch

- [x] 2.1 Test: one invalid document is skipped and the rest are analyzed; all invalid exits 2; the log carries no input values
- [x] 2.2 Per-item validation in `cli.main`, errors logged as `loc` and `type` only
- [x] 2.3 Mutation check — mutations: 7 tried, 7 caught

## 3. Rules and summary

- [x] 3.1 Test: negated R2 label fails, mid-text label is `uncertain`; R3 accepts `nie jest wykluczona utrata`; summary skips `not_applicable` rules
- [x] 3.2 R2 negation and prominence, R3 override patterns, summary wording
- [x] 3.3 Mutation check — mutations: 14 tried, 14 caught

## 4. Sentences and logging docs

- [x] 4.1 Test: `ok.` before an uppercase word ends a sentence, before a digit it does not; `2024 r.` does not
- [x] 4.2 Split `_ABBREV` into always / before-digit lists; `logging_setup` docstring and `analytics/CLAUDE.md` note on stderr
- [x] 4.3 Mutation check — mutations: 10 tried, 10 caught

## 5. Reviewer fixes

- [x] 5.1 Test: `nie tylko wyklucza straty` and `wykluczamy straty` are denials; negation stops at a line break and never applies to a hashtag; the look-back window does not cut inside a word; earliest mention in any form wins a tie; `tel. (22)` does not split
- [x] 5.2 R3 override and exclude patterns, R2 `negation_before` same-line and `pos`/`endpos`, registry earliest-mention position, `_DIGIT_NEXT`
- [x] 5.3 Mutation check — mutations: 11 tried, 11 caught

## 6. Closing

- [x] 6.1 Apply iw-docs-update (follow-ups, STATUS row) and add the iw-ai-log row
- [x] 6.2 Run iw-pr-review checks and fix real findings (iw-reviewer: 6 findings, all verified and fixed in group 5; declined items in `follow-ups.md`)
