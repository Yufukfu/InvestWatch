# Tasks

Rule for every group: `contracts/mocks/`, `contracts/mock-server/` and the `web/` mock mode are a test double and stay untouched. Tests read `documents.json` and `findings.json` only; a difference from the mock findings is recorded in `follow-ups.md`, never fixed in the mocks.

Prerequisite: `analytics-worker` is merged and this branch is rebased on `main` (proposal, Dependencies). Groups 1-5 are rules-only and do not need `analytics-llm-p0`. Group 6 starts only after `analytics-llm-p0` is merged (design decision 6).

## 1. Signal catalogues on the shared engine and evidence fields (≈ 1 h)

- [x] 1.1 Failing tests (`tests/test_signal_catalogue.py`): both catalogues load with the expected ids and `implemented` flags (S1.1-S1.7; S3.1-S3.8 with only S3.7 off), with `bias` and per-entry `weight`; a wrong prefix (`S3.2` in the M1 file, `S1.1` in `m2_rules.yaml`), a duplicate id, a weight `high`, a missing `bias`, an unknown param or a bad regex fail at load naming file and entry; `Rule.evidence_fields` defaults to `text`, a signal quoting `author.handle` / a link href / `url` passes the safety net, an M2 rule quoting the handle becomes `uncertain`; the sigmoid score (`σ(0) = 0.5` case, rounding, bounds)
- [x] 1.2 `rules/engine.py`: per-module id check, `weight`/`bias` read for M1/M3, signal param keys in `KNOWN_PARAMS`, `Rule.evidence_fields` in the safety net; `rules/scoring.py`; `rules/m1_signals.yaml` and `rules/m3_signals.yaml` with names from `contracts/mocks/generate_mocks.py`, weights and bias from design decision 7, and `llm:` blocks (Polish questions) on S1.4, S1.5, S3.3, S3.4; if `AdvertiserRef` is missing from `models.py` after the rebase, add it as in the worker branch; existing M2 tests stay green
- [x] 1.3 Mutation check; `mutations: 16 tried, 16 caught`

## 2. Link-host registry match, publisher identity and advertiser (≈ 1.25 h)

- [x] 2.1 Failing tests (`tests/test_registry.py`, `tests/test_advertiser.py`): referral link to a firm domain matches with 0.9 and the href as quote; malformed and non-http hrefs are skipped; a social page host never matches; `firm_own` ignores link hosts; publisher identity by profile host, non-social page host and normalized handle (`@alfainwestycje` yes, `@alfa_inwestycje_fan` no, social host never); advertiser from author, from page host (`website` set), malformed `profile_url` → null, 5000-character name cut to 200, `in_registry` equal to publisher identity, `on_warning_list` null
- [x] 2.2 Link-host matching in `registry.py` (used only for `third_party`/`unknown`); `modules/advertiser.py` (advertiser and publisher identity); tests green
- [x] 2.3 Mutation check; `mutations: 22 tried, 22 caught` (two first survivors, an empty normalized handle and a firm listing a social domain, got their own test cases)

## 3. M1 signals and finding (≈ 1.5 h)

- [ ] 3.1 Failing tests (`tests/test_m1.py`) for every scenario in `specs/m1-third-party-signals/spec.md`, on mocks `3c41441c…` and `182e5a42…` plus the hand-made cases (fuzzy-only, UTM only, `preferencje`, negated label, sponsored rel, past tense, author missing on a social post, bare mention below 0.6, S1.7 Polish-language-only, English ad of a Polish brokerage house)
- [ ] 3.2 `rules/m1.py` (S1.1-S1.7, S1.7 sharing the S3.6 detection; S1.5 rules-only `uncertain`; S1.4 `ask_llm` only on `pass`), dictionaries in `m1_signals.yaml`, `modules/m1.py` (score, Polish title and summary, `firm`, `advertiser`, `model`); tests green
- [ ] 3.3 Mutation check; `mutations: N tried, N caught`

## 4. M3 signals, S3.4 gate, M3 alongside M1 and finding (≈ 2 h)

- [ ] 4.1 Failing tests (`tests/test_m3.py`) for every rules-only scenario in `specs/m3-unauthorized-advice-signals/spec.md`, on mocks `007bbcee…`, `cdbf5306…` and `72acbb3b…` plus the hand-made cases (plain crypto, crypto CFD, `kupiłam`, English `.com` page, S3.8 crypto signal group, gate cases: S3.3 alone capped, S3.4 alone ≥ 0.7 via a fixed result, both strongest), and the "M3 alongside M1" attribution cases (`@trader_ola`, the firm's own offer, the two M1 mocks)
- [ ] 4.2 `rules/m3.py` (S3.1-S3.6, S3.8; S3.7 catalogue-only), dictionaries in `m3_signals.yaml`, `modules/m3.py` (score with the S3.4 gate, sentence-level attribution, Polish texts, `firm: null`, `advertiser`); tests green
- [ ] 4.3 Mutation check; `mutations: N tried, N caught`

## 5. Routing, pipeline and CLI (≈ 1 h)

- [ ] 5.1 Failing tests (`tests/test_pipeline.py`, `tests/test_cli.py`): the routing scenarios of `specs/document-analysis/spec.md` (`firm_own` matched → M2, unmatched → M3 or `no_signals`, firm's own social account → M2, `3c41441c…` → M1, English ad of a foreign firm → `not_targeting_poland`, English ad of a Polish brokerage house → M1, `007bbcee…` → M3, `8721cb75…` → `no_signals`, empty text → `empty_text`, link-host match → M1, malformed link → M3, finfluencer buy calls → M1 + M3); the M2 finding assembly scenarios (builder without a firm match, domain-only match); the CLI on `contracts/mocks/documents.json` exits 0 with M1, M2 and M3 findings that pass `contracts/validate.py finding`; every evidence on the six M1/M3 mocks is a substring of one of its rule's evidence fields
- [ ] 5.2 `modules/router.py` (publisher-and-registry routing), `pipeline.py` (link-host match for third-party documents, M1/M2/M3 dispatch with up to two findings, `no_signals`, `not_targeting_poland`, `module_not_implemented` removed), `cli.py` loads the signal catalogues; `pytest analytics` green; compare the CLI output for the six M1/M3 mocks with `contracts/mocks/findings.json` and record each difference (module, signal results, evidence, advertiser, score side of threshold) in `follow-ups.md` with a disposition; `git diff --stat -- contracts/ web/` is empty
- [ ] 5.3 Mutation check; `mutations: N tried, N caught`

## 6. LLM wiring for M1/M3 (≈ 45 min, after `analytics-llm-p0` is merged)

- [ ] 6.1 Rebase on `main`, re-read `llm/judge.py` and the `llm-analysis` spec; failing tests with the sibling's `FakeJudge` for the scenarios of the "LLM seam and rules-only degradation for signals" requirement (no judge, judge without verdicts, S3.4 confirmed on `cdbf5306…` reaching 0.7, only S1.5 asked on `3c41441c…`, S1.4 found by the LLM), the M3 "mass signals" comparison and "instrument recommendation alone" with a real verdict
- [ ] 6.2 Pass `judge`, `module` and `M1_CONTEXT` / `M3_CONTEXT` (M1 definition from the challenge; Art. 76 and the Art. 2-3 instrument list from annex 3, including whose offer it is) to `run_rules` in `modules/m1.py` and `modules/m3.py`; set `model.llm` as M2 does; tests green
- [ ] 6.3 Mutation check; `mutations: N tried, N caught`

## 7. Closing

- [ ] 7.1 Apply the iw-docs-update skill (`analytics/README.md` modules and signals, `.docs/analytics-plan.md` §2 routing and §6 S3.4 gate, the skeleton open question answered here, your own analytics row in `.docs/STATUS.md` unless the coordinating session still owns STATUS updates, ADRs: none expected, `docs-check` clean) and add the iw-ai-log row
- [ ] 7.2 Run the iw-pr-review skill and fix real findings
