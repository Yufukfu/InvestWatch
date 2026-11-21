# Follow-ups

Review findings and out-of-scope items, one row each (iw-commit-cycle step 8).

| # | Source | Item | Disposition |
|---|---|---|---|
| 1 | review groups 1-2 | `str.splitlines()` split gold lines on U+2028/U+0085 inside text | fix-here (`raw.split("\n")`, bytes read, test) |
| 2 | review groups 1-2 | duplicate JSON keys in `expect` / `rules` silently kept the last value | fix-here (`object_pairs_hook`, test) |
| 3 | review groups 1-2 | grid test recomputed the grid with the code's own expression | fix-here (literal tuple) |
| 4 | review groups 1-2, declined to judge | gold `fail` predicted `not_applicable` counts as `fn` and as an applicability error | wont-fix: intended (the rule missed a labeled violation, and the applicability mismatch is reported separately); documented in `metrics.rule_metrics` |
| 5 | review groups 1-2, declined to judge | gold `not_applicable` predicted `uncertain` counts toward `uncertain` and `applicability_errors` | wont-fix: both counts describe the prediction; confusion counts stay unchanged as the spec asks |
| 6 | review groups 1-2, declined to judge | per-rule metrics reuse the API's zero-division conventions | docs: stated in the eval README and `metrics.py` docstring |
| 8 | review groups 3-5 | an unescaped `@` in the password put part of it into the libpq host error, which reached the log | fix-here (exception class only, test with `se@cret`) |
| 9 | review groups 3-5 | one run id for all modules re-stored an unchanged module when another changed or with `--module` | fix-here (run id per module; spec and design updated) |
| 10 | review groups 3-5 | a run with a crashed gold document was stored with zero scores | fix-here (not stored, exit 1; spec scenario "Crashed gold document") |
| 11 | review groups 3-5 | an exception from the judge factory escaped as a traceback | fix-here (exit 2, class only in the log) |
| 12 | review groups 3-5 | `iw_app` needs UPDATE on `calibration_points` for the refreshed path | wont-fix: default privileges in `infra/postgres/init/01-app-role.sh` grant SELECT, INSERT, UPDATE, DELETE |
| 13 | gold set M2 (rules-only, worker base) | R2 returns `uncertain` when "Reklama." follows the headline instead of opening the page (`m2-r7-risk-behind-click`, `m2-r12-past-performance-compliant`, `m2-r13-past-performance-dominates`); ZASÓB asks only for an unambiguous label | new-item: R2 rule follow-up (prominence check on the first block / heading region instead of the first sentences); labels kept |
| 14 | gold set M2 | R3 `fail` on the two past-performance pages whose warning block directly follows a five-year results list: the sentence window is shorter than the list | new-item: R3 rule follow-up (count the claim's block, not sentences, when `blocks` exist); labels kept |
| 15 | gold set M2 | R3 `pass` where gold is `not_applicable` (`m2-r10-risk-in-polish`: "74% rachunków traci pieniądze" is a loss disclosure, not a return claim) | new-item: R3 claim exclusion for loss disclosures; does not change the score (pass) |
| 16 | gold set M2 | rules-only M2 at 0.5: precision 0.8, recall 0.2, because R4-R18 are not in this build | docs: expected; recall rises when `analytics-llm-p0` and `analytics-m2-p1-rules` land, with no gold-set change |
| 17 | gold set M1/M3, checked on `analytics-m1-m3` (6121a06) with this evaluation copied in | rules-only M3 never reaches its default 0.7: S3.4 needs the model and the cap keeps scores at 0.4-0.62, so 0.7 vs 0.9 changes nothing; moving 0.5 to 0.7 does (tp 3 to 0) | new-item for Damian: lower the M3 default or ship the LLM for S3.4 before the demo; the FP/FN scenario now checks 0.2 below or above the default |
| 18 | gold set M1 (stage-2 rules) | S1.2 misses a spoken promo code (`m1-promo-code-no-label`, "kod KOT50") and a `rel=sponsored` link without a query key (`m1-sponsored-blog`); S1.4 misses "Zakładajcie konto" / "Kupujcie" plural imperatives; S1.3 misses "Linki ... są partnerskie" | new-item: M1 dictionary follow-ups on `analytics-m1-m3`; labels kept |
| 19 | gold set M3 (stage-2 rules) | no M3 finding at all for `m3-polish-targeting-advice`, `m3-forex-mentoring` and the M3 half of `m1-m3-finfluencer-own-calls` (positives); S3.5 misses "Opłata 1% rocznie", "Pakiet ... za 1500 zł", "Prowizja od wyniku" | new-item: M3 routing and S3.5 dictionary follow-ups on `analytics-m1-m3`; labels kept |
| 20 | gold set M1/M3 | S1.5, S3.3 and S3.4 are `uncertain` rules-only, so their `strict` recall is 0 by design | docs: measured again with `--llm` once `analytics-llm-p0` ships its judge |
| 7 | group 5 | `--llm` looks for `investwatch_analytics.llm.judge_from_env` and `analyze(judge=...)`; `analytics-llm-p0` has neither yet, so `--llm` exits 2 on this build | new-item: when llm-p0 ships its judge, expose `judge_from_env()` (or adapt `_judge_factory`) and add a FakeJudge CLI test |
