# Tasks

Order R5, then R7, R8 and R13 (feature freeze Sun 08:00). If time runs short, ship the done groups with tests and record the rest in `follow-ups.md`. Tests read `contracts/mocks/*.json` and `eval/gold.jsonl` but never edit the mocks. Rule classes go in `rules/m2_visual.py`; `rules/m2.py` changes only in the detector (design 6).

## 0. Baseline

- [x] 0.1 Run `eval/run.py --module M2` (rules-only) on `origin/main` and record per-rule P/R and M2 at 0.1 in `follow-ups.md`.

## 1. R5 exposure and contrast

- [ ] 1.1 Write the failing tests (`tests/test_rules_m2_visual.py`): every R5 scenario, the catalogue parameter checks for `min_contrast`, and the implemented-rule list.
- [ ] 1.2 Add `rules/m2_visual.py` with the shared viewport helpers and R5, register it in `Catalogue.load`, add `min_contrast` to the catalogue. Tests green.
- [ ] 1.3 Mutation check; record `mutations: N tried, N caught`. Push the branch as a backup.

## 2. R7 one-click availability

- [ ] 2.1 Write the failing tests for every R7 scenario.
- [ ] 2.2 Implement R7. Tests green.
- [ ] 2.3 Mutation check; record `mutations: N tried, N caught`.

## 3. R8 responsiveness

- [ ] 3.1 Write the failing tests for every R8 scenario and the `min_font_px` check.
- [ ] 3.2 Implement R8. Tests green.
- [ ] 3.3 Mutation check; record `mutations: N tried, N caught`.

## 4. R13 dominance and the year-range detector

- [ ] 4.1 Write the failing tests for every R13 scenario and the "Past year range" scenario.
- [ ] 4.2 Add the closed year range to `_PastPerformance`, implement R13. Tests green.
- [ ] 4.3 Mutation check; record `mutations: N tried, N caught`.

## 5. Closing

- [ ] 5.1 Run `eval/run.py --module M2` again; record per-rule P/R and M2 at 0.1 next to the baseline in `follow-ups.md`; leave `test_eval_thresholds` as it is if the best threshold moved, and report.
- [ ] 5.2 Docs: `.docs/analytics-plan.md` §5, `.docs/status/` for analytics, the AI log entry, `docs-check` clean.
- [ ] 5.3 `iw-reviewer` pass on the whole diff; fix verified findings.
- [ ] 5.4 Archive the change as the last commit; push and open the PR to `main`.
