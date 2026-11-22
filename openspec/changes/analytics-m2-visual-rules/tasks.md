# Tasks

Order R5, then R7, R8 and R13 (feature freeze Sun 08:00). If time runs short, ship the done groups with tests and record the rest in `follow-ups.md`. Tests read `contracts/mocks/*.json` and `eval/gold.jsonl` but never edit the mocks. Rule classes go in `rules/m2_visual.py`; `rules/m2.py` changes only in the detector (design 6).

## 0. Baseline

- [x] 0.1 Run `eval/run.py --module M2` (rules-only) on `origin/main` and record per-rule P/R and M2 at 0.1 in `follow-ups.md`.

## 1. R5 exposure and contrast

- [x] 1.1 Write the failing tests (`tests/test_rules_m2_visual.py`): every R5 scenario, the catalogue parameter checks for `min_contrast`, and the implemented-rule list.
- [x] 1.2 Add `rules/m2_visual.py` with the shared viewport helpers and R5, register it in `Catalogue.load`, add `min_contrast` to the catalogue. Tests green.
- [x] 1.3 Mutation check; record `mutations: N tried, N caught`. Push the branch as a backup. `mutations: 13 tried, 13 caught` (visibility, the colour guard, the contrast boundary, best-of-viewport, worst viewport, the no-blocks guard, gamma, the ratio order, the quote; `min_contrast` bounds and the bool guard). The first run had one survivor (quote = raw block text); a mixed-block test was added.

## 2. R7 one-click availability

- [x] 2.1 Write the failing tests for every R7 scenario.
- [x] 2.2 Implement R7. Tests green.
- [x] 2.3 Mutation check; record `mutations: N tried, N caught`. `mutations: 7 tried, 7 caught` (the `false`/`true` tests, the partly-unknown downgrade, the per-viewport skip, the no-risk and no-blocks guards; first run one survivor, the no-blocks explanation is now asserted). R5 review fix (a colour outside `#rrggbb` is unknown, not a crash): `mutations: 1 tried, 1 caught`.

## 3. R8 responsiveness

- [x] 3.1 Write the failing tests for every R8 scenario and the `min_font_px` check.
- [x] 3.2 Implement R8. Tests green.
- [x] 3.3 Mutation check; record `mutations: N tried, N caught`. `mutations: 14 tried, 14 caught` (0 px, the 12 px boundary, clipped `true` and `null`, the visibility filter, the missing-viewport quote and locator, the one-viewport downgrade, worst viewport, best block, the no-risk and no-blocks guards; `min_font_px` bound and bool guard).

## 4. R13 dominance and the year-range detector

- [x] 4.1 Write the failing tests for every R13 scenario and the "Past year range" scenario.
- [x] 4.2 Add the closed year range to `_PastPerformance`, implement R13. Tests green.
- [x] 4.3 Mutation check; record `mutations: N tried, N caught`. `mutations: 15 tried, 15 caught` (the year-range end bound and the range itself; sentence and figure links; the visibility filter; largest-font tie; the first-block size bound and the first-block check; position vs list order; worst viewport; the quote; the three not-applicable cases). First run one survivor (sentence containment, redundant for `%` figures); an amount-only test was added. R13 review fix (a fee or tax percentage never links a headline; `blank_exclusions` as in the detector) and the coordinator's detector checks (non-gold year-range wording with an en dash, a range that is not over yet, R12b reads Polish "po opłatach" as a fee statement): `mutations: 4 tried, 4 caught`. Over the 69 gold and 10 mock documents the detector change alters 3 results, all on gold `m2-r13-past-performance-dominates`: R12a, R12b and R14 go from `not_applicable` to `pass`.

## 5. Closing

- [x] 5.1 Run `eval/run.py --module M2` again; record per-rule P/R and M2 at 0.1 next to the baseline in `follow-ups.md`; leave `test_eval_thresholds` as it is if the best threshold moved, and report.
- [x] 5.2 Docs: `.docs/analytics-plan.md` §5, `.docs/status/` for analytics, the AI log entry, `docs-check` clean.
- [ ] 5.3 `iw-reviewer` pass on the whole diff; fix verified findings.
- [ ] 5.4 Archive the change as the last commit; push and open the PR to `main`.
