# Design

## Context

`analytics/` is empty apart from a README and `CLAUDE.md`. The architecture is set by `.docs/analytics-plan.md` (§2 pipeline, §5 M2 rules, §12 skeleton plan) and ADRs 0301 (contracts v1), 0304 (LLM serving) and 0305 (thresholds). Contracts v1 are in `contracts/`, and mock documents and findings there show the expected shape. Integration #1 is Sat 17:00, so this change takes the shortest path to a pure, testable `document → findings` function. The I/O layer (worker, storage, events) comes in the next change.

## Goals / Non-Goals

**Goals:**
- Pure pipeline `analyze(doc, *, registry, catalogue, now) -> list[Finding]` with no I/O, deterministic given `now` and the id factory.
- Rules-only R1-R3 with exact-quote evidence, data-driven from `m2_rules.yaml`.
- Output that passes `contracts/validate.py finding`.

**Non-Goals:**
- Redis, Postgres, MinIO, events, thresholds, Docker (next change `analytics-worker`).
- LLM calls, embeddings, near-dup detection, topic gate (plan §2 step 2), M1 and M3.
- Visual rules R4-R8 and R13, even though the mocks carry `blocks`.

## Decisions

1. **Pydantic v2 for both contracts.** The input `ScrapedDocument` uses `extra="ignore"` so additive provisional fields from the scraper never break us. The output `Finding` uses `extra="forbid"` and contract enums as `Literal`s. The JSON Schema in `contracts/` stays the source of truth: a contract test validates model output against it when `CONTRACTS_DIR` is set and is skipped otherwise (plan §12.1). Alternative: generate models from the JSON Schema (`datamodel-code-generator`). Rejected because it adds a build step and a dependency for 2 models.
2. **Rules as classes, metadata in YAML.** Each rule is a subclass of `Rule` with `applies(ctx)` and `evaluate(ctx) -> RuleResult`. The name, severity, legal basis, dictionaries and the `implemented` flag live in `rules/m2_rules.yaml`, loaded once and validated, so the jury sees the full 18-rule catalogue and the path for adding a rule. The legal bases and Polish names are copied from `contracts/mocks/generate_mocks.py` so mocks and real output agree.
3. **Evidence from the original text.** Matching runs over the original `text` with case-insensitive regexes, where whitespace in a pattern becomes `\s+`. It never runs over the normalized copy, so every quote is a verbatim substring (the `CLAUDE.md` rule). Normalized text is used only for the hash and the language guess.
4. **Registry matching order:** exact name or alias with word boundaries in the text (confidence 0.95), then a page host equal to or a subdomain of `website_domains` (0.9), then fuzzy `rapidfuzz.fuzz.ratio` ≥ 88 between the name core (legal forms stripped) and word n-grams of the text of the same length (ratio/100 × 0.85; n-grams, not `partial_ratio`, so a name glued inside a longer word does not match). The best candidate wins. Legal-form stripping (`dom maklerski`, `biuro maklerskie`, `s.a.`, `sp. z o.o.`, `ltd`, `(oddział w polsce)`, `dm`) creates aliases automatically. CSV columns are `id, name, aliases, type, country, website_domains, source_url`, with list fields separated by `|`. The seed reuses the mock `registry_id`s so CLI output lines up with the dashboard mocks.
5. **Routing in this change:** `firm_own` → M2 even without a registry match. R1 then fails, which is the honest result for a page that does not name its firm. `third_party` / `unknown` → no finding and the log reason `module_not_implemented`. This differs from plan §2, which also requires a registry match for M2. A firm's own page that cannot be tied to the registry is still worth flagging.
6. **Score:** plan §5 formula with `uncertain` = 0.5. Unimplemented rules are omitted from `rules[]`, not reported as `pass`, so the dashboard never shows a check that never ran.
7. **R3 window:** the claim and warning dictionaries and `window: 2` live in YAML. Footnote-marked warnings (leading `*`, `¹`, `²`, `³`) don't count. This is the regex version, and the LLM decides borderline cases later (plan §5).
8. **Ids and time:** `Finding.id` is uuid4 and `detected_at = updated_at = now` (UTC, injected). Turning a re-scan into an update instead of a duplicate is a storage concern for the next change.
9. **Logging:** stdlib `logging` with a JSON formatter to stdout, no `print` (root `CLAUDE.md`). The CLI writes findings to stdout through `sys.stdout.write`, which is output, not logging.

No ADR: none of these choices is hard to reverse. They are local to `analytics/` and follow the accepted plan and ADRs.

## Risks / Trade-offs

- [Regex R3 is coarse: percent figures that are not returns, for example "0% prowizji", produce false claims] → keep the claim dictionary in YAML, add negative test cases, and let the LLM layer refine it later.
- [The fuzzy match produces false firm matches on short names] → fuzzy matches compare whole word n-grams and need ratio ≥ 88, so a short name needs an exact word (which the name match already catches); the confidence goes into the finding.
- [Models drift from the JSON Schema] → the contract test runs in CI with `CONTRACTS_DIR=contracts`.
- [Mock expectations differ from rules-only results: the mock EuroTrade R3 is `uncertain` from the LLM, while rules-only gives `pass` within the window] → mocks are illustrative, not a gold set. The tests assert only the scenarios in the specs.

## Open Questions

- Whether `firm_own` pages without a registry match should go to M3 too. Revisit when M3 lands.
