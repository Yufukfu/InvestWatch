# Follow-ups

## Rule results that differ from the mock findings

`contracts/mocks/findings.json` stays as the web test double and is never edited or regenerated (Damian's rule). The rows below are differences expected from the specs of this change. Task 13.0 checks them against the real CLI output and adds any new ones. Each row's disposition is `keep-mock`: the mock is illustrative, and the rule follows ZASÓB and the specs.

| # | Mock document | Mock result | Expected from this change | Why |
|---|---|---|---|---|
| 1 | `m2-alfa-landing` (`a3c88321`) | R3 `fail`, `method: hybrid` | R3 `fail`, `method: rule` | A footnote-only warning is never deferred to the LLM (R3 requirement; ZASÓB: the warning must "bezpośrednio towarzyszy" the claim). |
| 2 | `m2-alfa-landing` | R5 `fail`, R8 `fail` | not in `rules[]` | R5 and R8 are P1 and not implemented here. |
| 3 | `m2-alfa-landing` | R17 `fail`, `method: llm` | rules-only: R17 `pass`; with the LLM: whatever the judge decides (`hybrid`) | A bare "pod nadzorem KNF" is not a violation on its own (ZASÓB). Only the LLM classifies the use. |
| 4 | `m2-alfa-landing` | R18 `fail`, `method: llm` | R18 `fail`, `method: rule` | A safety word in the same sentence as the supervisor mention is a deterministic fail that is not deferred. |
| 5 | `eurotrade` (`c99e2a35`) | R3 `uncertain`, `method: llm` | rules-only R3 as the skeleton computes it; LLM only if the case is near-window | R3 is deferred only in the borderline proximity case. |
| 6 | `eurotrade` | R7 `fail`, R15 `fail` | not in `rules[]` | R7 and R15 are P1. |
| 7 | `eurotrade` | no R4, no R6 | R4 `not_applicable` (the risk block has `visible: false`, which is R5's concern); R6 `pass` (the risk block is in `region: main`) | R4 measures only visible risk blocks. R6 judges placement only, not visibility or interaction. |
| 8 | `m2-bank-ok` (`5030107e`) | R4, R6 `not_applicable` only; score 0.12 | also R10 `pass`, R14, R17, R18 `not_applicable`; score 0 | More rules are implemented, and none fails. |
| 9 | all M2 mocks | `model.llm: gemma3:4b`, `embedder: bge-m3` | `model.llm` is the configured model only when an LLM verdict was merged, otherwise `null`; `embedder: null` | `model.llm` reflects actual LLM use (M2 finding assembly requirement). There are no embeddings in this change. |

## Review findings

| # | Source | Item | Disposition |
|---|---|---|---|
| R1 | review group 1 | `_YEAR` read amounts like `2000 zł` as years | `fix-here`: a year counts only in a year context (`w/za/od 2025`, `2025 r.`, `2025 roku`) |
| R2 | review group 1 | Offer deadlines and imperative promises in the fetch year (`do końca 2026`, `Zyskaj 20% w 2026 roku`) read as past performance | `fix-here`: future markers `zyskaj`, `zarabiaj`, `możesz`, `nawet`, `ważn…`, `do (końca) <date/year>` |
| R3 | review group 1 | Non-return percentages (share of clients or accounts, bonuses, the ESMA CFD warning `74% rachunków…`) read as return figures | `fix-here`: R14-only `figure_extra_exclude_patterns` |
| R4 | review group 1 | The aliased R3 exclude list silently changes R14 | `fix-here`: comment on the anchor; R14-only excludes live in their own key |
| R5 | review group 1 | Disclaimers missed: `Osiągnięte w przeszłości wyniki nie gwarantują…`, `Past results / Historical returns are not indicative…` | `fix-here`: two disclaimer patterns (shared with R6) |
| R6 | review group 1 | No test with a past and a future marker in one sentence | `fix-here`: test added |
| R7 | review group 1 | tasks.md 1.2 named the wrong parameter keys | `fix-here` |
| R8 | review group 1, declined | `\bcel\w*\b` also matches `celowo`, `celny` | `wont-fix` for now: low impact, it only makes a year-only sentence not past performance |
| R9 | review group 1, declined | Absolute-amount past returns (`przyniósł 5 000 zł zysku`) are not return figures | `new-item`: decide with the gold set whether R14 needs amounts |
| R10 | review group 1, declined | R3 shares the percentage false positives (bonus, share of clients) | `new-item`: R3 claim excludes, outside this change's R3 scope |
| R11 | review group 2 | `_YEAR` still read an amount after a preposition (`od 2000 zł`, `z 2000 zł`, `za 2000 PLN`) as a year | `fix-here`: currency lookahead after the year |
| R12 | review group 2 | `ważn…` as a future marker hid real past performance (`Ważne: …12% w 2024 r.`) | `fix-here`: narrowed to `ważn… do`; `dał/dała…` added as past verbs |
| R13 | review group 2 | R6 (and R4) quoted the whole block, not the risk sentence | `fix-here`: `warning_quote` quotes the first warning sentence inside the located block |
| R14 | review group 2, declined | A current-year promotion (`Lokata 7% w 2026 r.` fetched in 2026) counts as past performance | `wont-fix` for now: follows the spec's "not later than the fetch year"; revisit with the gold set |
| R15 | review group 2, declined | A viewport with blocks but no risk block is skipped (warning missing on desktop, exposed on mobile gives `pass`) | `new-item`: a warning missing from a whole viewport is R8 (responsiveness, P1) |
| R16 | review group 2, declined | A footnote-marked block in the main region and in view on load passes R6 | `wont-fix`: follows the spec's AND rule (placement and not in view) |
| R17 | review group 2, declined | The `hiding_regions` default is in both the code and the YAML | `wont-fix`: the YAML is the source; the code default only guards a missing key |
| R18 | review group 2, can't verify | Whether the scraper fills `region` and `in_viewport_on_load`; without `region`, R6 passes | `new-item`: confirm with Adam when the `blocks` shape is settled |
| R19 | review group 3 | The currency lookahead `tys` also matched `tysiące`, so real past performance was missed | `fix-here`: `tys(?:\.|\b)` |
| R20 | review group 3 | A 0 px median forced the ratio to 1.0 (pass); negative sizes were measured | `fix-here`: blocks of 0 px or less never set the dominant size; a visible risk block with no positive size gives `uncertain` |
| R21 | review group 3 | The displayed ratio was rounded (`0,75×` on a fail against 0,75) | `fix-here`: truncated to 3 decimals |
| R22 | review group 3 | The R4 requirement said "the risk block's text" while the code quotes the warning sentence | `fix-here`: spec and design updated |
| R23 | review group 3, can't verify | Container blocks from the scraper (body plus warning in one block) make R4 pass on the container's size | `new-item`: with follow-up R18 (block granularity, Adam) |
| R24 | review group 3, declined | The lower weighted median makes R4 lenient on a 50/50 split | `wont-fix` for now: threshold policy for the gold set |
| R25 | review group 3, declined | The loader ignores unknown top-level YAML keys (`shared:` lists no rule references are never validated) | `wont-fix`: predates the change; `test_catalogue_is_complete` catches a mistyped `rules:` key |

## Mock divergences observed after task groups 1-4 (CLI, rules-only)

`python -m investwatch_analytics.cli contracts/mocks/documents.json` at the group 4 tip. The output passes `contracts/validate.py finding`, and `contracts/mocks`, `contracts/mock-server` and `web` are unchanged. All rows are `keep-mock`.

| Mock document | Mock | Ours | Note |
|---|---|---|---|
| `m2-alfa-landing` | score 0.86 | score 0.722 | R5, R8 (P1) and R10 (group 11) are not in `rules[]` yet; R17 passes rules-only (row 3 above) |
| `m2-alfa-landing` | R14 absent | R14 `not_applicable` | no past performance in the text |
| `eurotrade` | R1 `pass` | R1 `fail` | Pre-existing since `analytics-skeleton`: the page text never names the firm (domain match only), which the R1 spec scenario "Matched by domain only" makes a `fail` |
| `eurotrade` | R2 absent | R2 `fail` | Pre-existing: the page has no ad label |
| `eurotrade` | R3 `uncertain` (llm) | R3 `pass` (rule) | Pre-existing: the English warning is within the ±2 window |
| `eurotrade` | R10 `fail` | not in `rules[]` | R10 is group 11 |
| `eurotrade` | score 0.74 | score 0.538 | Follows from the rows above |
| `m2-bank-ok` | R3 `pass` | R3 `not_applicable` | Pre-existing: no return claim in the text |
| `m2-bank-ok` | score 0.12 | score 0 | Nothing fails |

## Review findings, group 4

| # | Source | Item | Disposition |
|---|---|---|---|
| R26 | review group 4 | R17 deterministic false fails: `Rada Nadzorcza zatwierdziła…`, negated approval (`KNF nie zaaprobował…`), the lawful prospectus statement, `certyfikat ISO … i podlega nadzorowi KNF` | `fix-here`: supervisory board and `nadzorowany przez <non-supervisor>` are not mentions; approval excludes (negation, prospectus); `certyfikat` only of the supervisor; spec updated |
| R27 | review group 4 | R18 missed `Bezpieczeństwo … gwarantuje nadzór KNF` | `fix-here`: `bezpieczeństw…` and `gwarant…`; a negated guarantee (`nie gwarantuje bezpieczeństwa`) is excluded |
| R28 | review group 4 | `nadzorowany przez doświadczonych zarządzających … bezpieczny` was an R18 fail | `fix-here` (with R26) |
| R29 | review group 4 | `licencję na oprogramowanie`, `rynek regulowany` were supervisor mentions (wasted LLM calls later) | `fix-here`: `licencja` only of a supervisor or for brokerage activity, `regulowany przez` |
| R30 | review group 4 | An unhashable `llm.when` raised `TypeError` instead of a catalogue error | `fix-here` |
| R31 | review group 4, plausible | `Fundusz nadzorowany przez KNF, środki chronione przez system rekompensat.` is an R18 fail; a factual compensation-scheme statement may be lawful | `new-item`: product question for Damian (calibration with the gold set) |
| R32 | review group 4, can't verify | Group 8 must skip R17's deterministic fail under `when: always`, and decide whether an LLM `pass` without a quote replaces the rules-only evidence | `fix-here` in group 8 (R17 `ask_llm` override; merge keeps rules evidence when the verdict has none) |
| R33 | review group 4, declined | English variants (`regulated and authorised by`, `licensed by`) | `new-item`: extend with the gold set |

## Coordinator answers applied (fix commit after group 4)

| # | Answer | Change |
|---|---|---|
| R31 → resolved | The investor-compensation-scheme fact next to KNF is lawful mandatory information, not R18. R18 is supervision "używane do sugerowania bezpieczeństwa inwestycji" | `fix-here`: `chronione przez system rekompensat` is excluded from R18's safety words. A safety claim in the same sentence still fails; borderline cases go to the LLM (`llm:` block) |
| R9 → resolved | Past results in any unit are past performance | `fix-here`: R14 counts an amount (`5 000 zł`, `1200 PLN`) next to return vocabulary as a return figure. A bare amount (bonus, fee, subscription) does not count |
| R18 → resolved | The scraper on `main` does not produce `blocks` yet (no Playwright rendering) | Verified: R4 and R6 are `not_applicable` without blocks on every mock. `fix-here`: R6 never passes on missing metadata. A block with `region: null` (and no footnote marker, not in view on load) is unknown. All unknown gives `not_applicable` "brak metadanych renderowania"; unknown next to hidden gives `uncertain`. R4 reads only fields the contract requires (`text`, `font_size_px`, `visible`, `viewport`), so it cannot see a null |

## Adversarial-input timing (ReDoS check, coordinator request)

Every regex that R3, R4, R6, R14, R17 and R18 use (107 patterns) was timed on 14 adversarial inputs, each 20k and 40k characters long. The inputs were long whitespace, tab and newline, letter, digit, dot, Polish-letter and punctuation runs, plus repeated `nie `, `bez `, `wynik `, `nadzór przez `, `1,` and `12,5 `. `locate()` was timed too.

| # | Finding | Disposition |
|---|---|---|
| R34 | `\d+(?:[.,]\d+)?\s?%` and the three excludes built on it were quadratic on a long digit run: about 25 s at 20k digits, about 4× slower when the input doubled. This includes R3's claim and exclude lists, which R14 aliases | `fix-here`: `(?<!\d)` prefix, so the pattern is tried once per number, not once per digit; regression tests on 20k-digit inputs (< 2 s). After the fix no pattern is super-linear |
| R35 | `locate()`'s whitespace-insensitive search is O(text × needle) on a huge block | `fix-here`: only block texts up to `LOCATE_FUZZY_MAX` (2000 chars) go through the fuzzy path; longer ones match exactly or give null evidence |
| R36 | `preprocessing._BOUNDARY` is quadratic on long whitespace runs (Kacper) | `docs`: fixed on `analytics/analytics-worker` by the worker session, arrives with the next sync; not touched here |

## For the PR body

- Commits `f7e07d0..672d927` (11 commits, from the R6 commit to the ReDoS fix) have an `m2_rules.yaml` that does not load. This is an artefact of the conflict resolution during the rebase onto `analytics-worker` 9bd27e8: a joined line and a dropped `shared:` block. `55a578e` repairs it. CI runs on the PR head only. The coordinator decided not to rewrite the history again (2026-11-21).
- `egress` is re-added to `analytics/compose.yaml` together with the hosted-LLM client (group 12). Kacper's #26 review removed it until the client existed.

## Review findings, group 5 (focus: security)

| # | Source | Item | Disposition |
|---|---|---|---|
| R37 | review group 5 | A slow-drip server kept a call alive far past `LLM_TIMEOUT_S` (httpx timeouts are per read); the response size was unbounded | `fix-here`: streamed read with a total deadline and a 1 MB cap (`MAX_RESPONSE_BYTES`) |
| R38 | review group 5 | A server trickling the response *headers* is still bounded only per read | `wont-fix` for now: a hard deadline needs an async client; the per-document budget and the breaker still cap the damage between calls |
| R39 | review group 5 | Userinfo in `LLM_BASE_URL` reached httpx's INFO log and replaced the Bearer key | `fix-here`: credentials, query and fragment in `LLM_BASE_URL` are a config error; the message never quotes the URL |
| R40 | review group 5 | A malformed `LLM_BASE_URL` degraded silently forever | `fix-here`: http(s) with a host required; a key over plain http to a non-local host is refused |
| R41 | review group 5 | The test guard let any loopback port through (a developer's real local Ollama) | `fix-here`: only ports registered by the stub (and the closed-port helper) pass |
| R42 | review group 5 | `trust_env` defaulted to on (proxy, netrc, CA bundle from the environment) | `fix-here`: `trust_env=False` |
| R43 | review group 5, declined | 400/404/422 count toward the breaker; one oversized prompt rejected by Ollama could open it | `new-item`: revisit with real Ollama behaviour in task 12.4 |
| R44 | review group 5, declined | Transitive deps of httpx are not pinned; `pyproject.toml` lists no runtime deps | `wont-fix`: same pattern as the other services; pip-audit runs on the resolved set |

## Review findings, group 6 (focus: security)

| # | Source | Item | Disposition |
|---|---|---|---|
| R45 | review group 6 | With long sentences the 4-sentence overlap advanced one sentence per chunk (4 chunks covered ~23% of a long page), and before a long sentence it produced duplicate subset chunks | `fix-here`: overlap capped at half a chunk, every chunk must end later than the previous one (`_next_start`); spec, design and ADR 0310 updated |
| R46 | review group 6 | Look-alike tags escaped neutralizing: fullwidth/angle-quote brackets, fullwidth letters, zero-width or soft-hyphen inside `document`, `&lt;`/`&#60;` entities, newline or 9+ spaces inside the tag | `fix-here`: widened `_TAG` (one gap and an optional slash-with-gap, so it stays linear) |
| R47 | review group 6 | `prompt_version` covered only the system message; a changed chunk size could serve answers for different chunk text | `fix-here`: `USER_FORMAT` is hashed into the version; the chunk span goes into the cache key (group 10, design §7) |
| R48 | review group 6 | `split_chunks` had no guard for `chunk_chars < 1` and built every slice of a huge sentence before the cap | `fix-here` |
| R49 | review group 6 | Two checks with the same rule id kept input order | `fix-here`: sorted by (rule id, question, allowed); the engine also never sends a rule id twice (group 8) |
| R50 | review group 6, declined | Whether a 4B Gemma obeys "ignore instructions"; a random-nonce delimiter instead of the fixed tag | `wont-fix`: the defence is that only deferred checks reach the model and quotes are verified; the spec fixes the tag |

## Review findings, groups 7 and 8 (focus: security)

| # | Source | Item | Disposition |
|---|---|---|---|
| R51 | review group 7 | `re.escape`, `strip()` and the exact-match branch of `verify_quote` were not pinned by tests (3 surviving mutants against the recorded 18/18) | `fix-here`: tests for metacharacters, padding (padding no longer bypasses the 8-char minimum), exact match preferred over a near-variant |
| R52 | review group 7 | The whitespace-insensitive fallback could return evidence far longer than the quote (a huge whitespace run) | `fix-here`: a match over 2 × 400 chars is rejected |
| R53 | review group 7 | An explanation of only control characters became `""` | `fix-here`: fixed Polish fallback text |
| R54 | review group 7 | Small models send `""` for "no quote", which turned every `pass` into `uncertain` | `fix-here`: a blank quote is no quote |
| R55 | review group 7, for the web layer | `explanation` keeps HTML, Markdown and URLs; `evidence` is verbatim document text and may carry bidi/control characters | `new-item` (Kacper): HTML-escape both, never render as Markdown/HTML, no auto-linking; render evidence with `dir="auto"` / `<bdi>` |
| R56 | review group 8 | A rule-class `ask_llm` override that skips `super()` could defer a rule without an `llm:` block and crash `_refine` | `fix-here`: the engine checks `spec.llm is not None` itself |
| R57 | review group 8 | A merged verdict kept the rules-only `evidence_locator` | `fix-here`: cleared when the evidence changes |
| R58 | review group 8 | Task 8.1 "S-ids accepted for non-M2 catalogues" is not in this branch's loader | `docs`: provided by #35 (`_ID_PREFIX`); this branch's tests build S-id catalogues directly |
| R59 | review group 8, for the #35 merge | `RuleSpec` gains `llm` here and `weight` in #35, and #35's loader passes `weight` by position | `fix-here` at the merge: pass `weight=` and `llm=` by keyword; default `run_rules(module=catalogue.module)` once #35's `Catalogue.module` exists |
| R60 | review group 8, declined | With `when: always`, an M3 LLM verdict can open or close #35's M3 gates, and the M3 call runs before those gates | decided, see below |

## Coordinator decisions and task 12.4 (hosted Gemma 4)

| # | Source | Item | Disposition |
|---|---|---|---|
| R60 | decided by Damian, 2026-11-21 | M3 LLM call before #35's gates | closed: "Tylko gdy reguły coś znalazły". S3.3 and S3.4 are `when: uncertain` (their rules return `uncertain` exactly on a candidate), so no M3 request without an M3 rule signal; a test pins it. Reason: it saves the Gemma quota, and an M3 found by the LLM alone is out of scope for the hackathon |
| R61 | task 12.4 | Hosted Gemma 4 prefixes every answer with `<thought>…</thought>`, even in JSON mode | `fix-here`: the client strips one leading thought block (and a ```json fence); any other wrapper stays malformed (ADR 0317) |
| R62 | embeddings-session review | A deeply nested JSON body raised `RecursionError` out of the client | `fix-here`: every parse error is `LlmMalformed` |
| R63 | embeddings-session review | `LLM_BASE_URL` with a bad port or embedded whitespace passed startup | `fix-here`: the port is read during the check; whitespace and control characters are a config error |
| R64 | task 12.4 | Gemma 4 latency (15-60 s) exceeds the default `LLM_TIMEOUT_S=20` | `docs`: ADR 0317 and `.env.example` give `LLM_TIMEOUT_S=45`, `LLM_DOC_BUDGET_S=50`, `CLAIM_MIN_IDLE_MS=90000` for the hosted Gemma; the defaults stay for faster endpoints |
| R65 | full suite | The new M2 rules pushed `test_redos.py::test_r3_patterns_are_fast_on_hostile_input[claim-warning-pairs]` (an absolute 3 s limit on 16,000 sentences) over its limit | `fix-here`: R14 checks the cheap past marker before the figure, R14/R17/R18 use one alternation per pattern list and a raw pre-check; the test now passes on its own. Its flakiness under load is the separate main-branch fix the coordinator named (ratio-based timing), not changed here |
| R66 | ADR 0316 procedure | The re-measured M2 default threshold is 0.1 (was 0.25): more applicable, passing rules lower the M2 scores | `fix-here`: `eval/thresholds.json`, `events.DEFAULT_THRESHOLDS` and the API's `DEFAULTS` updated; `new-item` for Damian: check that 0.1 is acceptable for the demo |
| R67 | cut plan | R10 (language consistency) and the per-sentence language guess were not built | `new-item`: a follow-up change; the R10 requirement and the Preprocessing delta were removed from this change's specs, and R10 stays `implemented: false` |
| R68 | ADR 0317 | Whether a small Gemma 4 build exists for Ollama | `new-item`: not checked; `gemma3:4b` stays the local swap target |
| R69 | task 12.4 | About half the hosted calls returned 503 "high demand" on 2026-11-21 | `docs`: the demo must pre-warm the cache and keep the Ollama profile ready (ADR 0317) |

## Whole-branch review (focus: security)

| # | Source | Item | Disposition |
|---|---|---|---|
| R70 | whole-branch review | `evaluation --llm` looked up `llm.judge_from_env`, which did not exist (spec `gold-set-evaluation`; analytics-eval-calibration follow-up 7), and the report read `judge.model` | `fix-here`: `llm.judge_from_env()`; the report reads `model_name` |
| R71 | whole-branch review | `analytics/README.md` and `api/README.md` still said M2 0.25 | `fix-here`: the evaluation table row and both defaults updated to the re-measured numbers |
| R72 | whole-branch review | A timeout that the document budget cut short was logged as `llm_timeout` and counted for the breaker | `fix-here`: it is `llm_budget_exhausted` and does not count; a plain timeout still does |
| R73 | whole-branch review | The budget check left no room for the 3 s connect timeout | `fix-here`: `LLM_DOC_BUDGET_S + 3 s` must stay below `CLAIM_MIN_IDLE_MS` |
| R74 | whole-branch review, declined | M1 sends S1.4/S1.5 (`when: always`) on every M1 document, the quota concern R60 settled for M3 | closed, decided by Damian (2026-11-22): S1.4/S1.5 stay `when: always`. Routing already requires a registry firm mentioned by a third party, and S1.5 has no rule-based answer |
| R75 | whole-branch review, residual risk | A `pass` without a quote is allowed (spec), so an injected document can clear a deferred check (R3 borderline, S3.3/S3.4 gate) | `docs`: accepted design (ADR 0309: only deferred checks are reachable); named in the PR body |
| R76 | whole-branch review, could not check | Real Gemma `<thought>` variants (leading whitespace, other case) and the real-Redis cache path | `new-item`: watch the logs for `llm_malformed` after deploy; run the cache with `TEST_REDIS_URL` |
| R77 | re-review of the R72 fix | Treating every timeout as the budget's when the read timeout had been shortened hid early (connect) timeouts from the breaker; with `LLM_TIMEOUT_S >= LLM_DOC_BUDGET_S` the breaker could never open on a dead endpoint | `fix-here`: a timeout is the budget's only when the budget has actually run out; the docs state the 3 s margin |
