# Proposal

## Why

Stage 3 (etap 3) of analytics. It builds on stage 2, the change `analytics-llm-p0` (local branch `analytics/analytics-llm-p0`, not merged), which adds R4, R6, R10, R14, R17 and R18, the `llm:` catalogue blocks and the judge seam (`run_rules(…, judge=…)`, `Rule.ask_llm`, merge with `method: llm | hybrid`). After stage 2, M2 still leaves out the text rules that the challenge criteria name for past performance, forecasts, comparisons and tax (ZASÓB R11, R12a, R12b, R15, R16). The jury scores against those 18 criteria. Two of them, R11 and R15, say that a detection is flagged in the report, so a material that compares products or forecasts results without breaking a rule still has to show the detection.

Damian approved this change as the lowest priority of stage 3. Implementation starts only after `analytics-llm-p0` task groups 5-12, on the coordinator's go.

This change is planned on top of `analytics/analytics-llm-p0` so that its design follows that branch's rule engine. **It will be rebased onto `main` once its parents merge**: `analytics-worker` (PR #26), then `analytics-llm-p0`. It is kept apart from that in-flight work. It does not touch the branches or worktrees of `analytics-worker`, `analytics-m1-m3` or `analytics-llm-p0`, and it does not edit the STATUS files.

## What Changes

The rules follow the challenge's criteria document `doc/ZASÓB DLA UCZESTNIKÓW - InvestWatch - kryteria oceny informacji o ryzyku.docx` (cited as ZASÓB), whose wording and legal basis each requirement quotes. Every new rule:
- runs rules-first;
- quotes verbatim evidence;
- is `not_applicable` without its trigger;
- counts a violation once, in the rule that names it (the principle from `analytics-llm-p0` design §1a and its resolved questions 4 and 6).

The new rules:
- **R11 product comparisons** (ZASÓB: "Wykrywa porównania produktów i usług, weryfikuje źródło informacji, przyjęte założenia i flaguje naruszenia w raporcie"; art. 44 ust. 3). It detects comparisons with other products, services or providers (index and benchmark comparisons are an extension; inflation is out) and checks that a source and the assumptions are given. ZASÓB flags only violations, so a compliant comparison is a plain `pass` that stores the quoted comparison, without a flag. A superlative with no comparator and no source is `uncertain`, with the missing source named as the reason. A source given without assumptions is also `uncertain`. Its `llm:` block (`when: uncertain`) sends these cases to the LLM.
- **R12a past performance, period and scope** (ZASÓB: "obejmują okres ostatnich 5 lat … pełne okresy 12-miesięczne; oraz czy wskazano okres referencyjny i źródło"; art. 44 ust. 4). It runs on the past-performance sentences that R14 already detects. It evaluates three named sub-checks, and its result and explanation name the one that failed:
  - 5 years and full 12-month periods;
  - the reference period;
  - the source.

  "Od początku działalności" with no dates fails the reference-period sub-check outright. Only the 5-year sub-check can be `uncertain`: a dated since-inception period is allowed only when the product is younger than 5 years, and the rules cannot check that. Its `llm:` block (`when: uncertain`) handles that case.
- **R12b past performance, currency and costs** (ZASÓB: "ostrzeżenie o wpływie zmian kursów walutowych oraz czy wskazano wpływ prowizji, opłat i obciążeń"; art. 44 ust. 4). The statement of how fees, commissions and charges affect the results is always required when past performance is shown. The currency warning is required only when the past results are given in a currency other than PLN: ZASÓB states no condition, but art. 44 ust. 4 lit. e does, and the rule's explanation cites that article so a juror who reads ZASÓB sees why. It is rules-only.
- **R15 forecasts** (ZASÓB: "Rozpoznaje prognozy i sprawdza, czy zawarto wyraźne ostrzeżenie… Flaguje w raporcie wykrycie prognozy"; art. 44 ust. 6). It detects forecasts of future results, needs the warning that a forecast is not a reliable indicator, and reports every detected forecast. A figure tied to a future period (`w 2026 zarobisz…`, `w przyszłym roku spodziewamy się…`) is a forecast. A promotional imperative (`Zarabiaj nawet do 18% rocznie`) is not: it is R3's return claim. A compliant forecast is a `pass` that quotes the forecast and says it was detected. A weak future marker (`będzie`, `will`) with result vocabulary but no figure is `uncertain`. Its `llm:` block (`when: uncertain`) handles that case.
- **R16 tax information** (ZASÓB: "Jeśli reklama odwołuje się do traktowania podatkowego, sprawdza obecność wyraźnej informacji o zależności od indywidualnej sytuacji klienta i możliwości zmian"; art. 44 ust. 7). When the material refers to tax treatment (`IKE`, `IKZE`, `podatek Belki`, `zwolnienie z podatku`, `tax`), it needs both parts: the individual situation and the possibility of change. It is rules-only.

Shared work:
- **Count once:** R12a, R12b and R14 share one past-performance detector, so all three are `not_applicable` together and no rule re-checks another rule's element of art. 44 ust. 4. ADR 0315 records this, together with the ownership map of each element and the reporting convention: R15 flags every detected forecast, while R11 flags only violations.
- **ReDoS-safe regexes:** every catalogue pattern, new and existing, is checked at catalogue load. The loader rejects nested unbounded repetition such as `(\w+\s*)+`. A test also times every catalogue pattern and every module-level regex in `rules/m2.py` on adversarial input. This follows a ReDoS that Kacper found in preprocessing.
- **Catalogue:** the entries for R9, R11, R12a, R12b, R13 and R16 get the legal basis that ZASÓB gives them. R11, R12a, R12b, R15 and R16 become `implemented: true`.

**Out of scope:**
- The visual rules R5, R7 and R8, which need scraper `blocks` (issue #29).
- R13 (dominance of past performance). ZASÓB asks whether past performance is "najbardziej wyeksponowanym elementem". Measuring prominence needs `blocks` (font size and position), so R13 waits with the visual rules for #29. A text-only proxy, such as past performance in the first sentence, was judged too noisy to ship.
- R9 (comprehensibility for the target group). ZASÓB asks for a judgement in "język zrozumiały dla przeciętnego odbiorcy". No cheap deterministic signal covers this: sentence length and jargon lists flag lawful warnings. R9 is marked in the catalogue for a later LLM-first change and stays `implemented: false`.
- Changes to the LLM layer itself (client, prompt, chunking, cache). This change only adds `llm:` blocks that the stage-2 seam already supports.
- Preprocessing. Kacper's ReDoS finding there is fixed wherever he reported it, not here.
- The Polish summary sentence of the M2 finding. The detections are reported in `rules[]`, as follow-up F3 explains.
- The mocks. `contracts/mocks/`, `contracts/mock-server/` and the `web/` mock mode stay untouched (Damian's rule). Every difference from `contracts/mocks/findings.json` is recorded in `follow-ups.md`.

**Owner:** Damian (`analytics/`).

**Contracts:** the change touches no contract, REST route or event. It fills the `rules[]` entries that `Finding` v1 already allows (`rule_id` R11, R12a, R12b, R15, R16), so it needs no version bump.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `m2-compliance-rules`: the catalogue requirement changes. There are more implemented rules, `llm:` blocks on R11, R12a and R15, a ZASÓB legal basis for every entry, and the regex-safety check at load. New requirements cover R11, R12a, R12b, R15 and R16.

## Impact

- **Code, under `analytics/` only:**
  - `rules/m2.py`: new rule classes R11, R12a, R12b, R15 and R16, plus a `_PastPerformance` base that R14 now uses with unchanged behaviour.
  - `rules/m2_rules.yaml`: dictionaries, anchors and `llm:` blocks.
  - `rules/engine.py`: new parameter keys in `KNOWN_PARAMS`, and the nested-quantifier lint in `_check_params`.
  - `tests/test_rules_m2_p1.py` and `tests/test_regex_safety.py`.
- **Dependencies:** none.
- **ADRs:** 0315 (ownership of the art. 44 elements among the M2 rules, and how R11 and R15 report a compliant detection).
- **Docs:**
  - `.docs/analytics-plan.md` §5: the R9, R11, R12a, R12b, R13, R15 and R16 rows, with their status and with R13 marked as visual.
  - `analytics/README.md`: the list of rules.
  - The STATUS rows are updated by the coordinator, not this change.
- **Sequencing:** the rule groups (1-6) need only the stage-2 rule engine and R14, which are already on `analytics/analytics-llm-p0`. Group 7 tests the `llm:` blocks against the judge seam, so it needs task group 8 of `analytics-llm-p0`. If that group is cut, the blocks stay inert and the rules-only results stand.
