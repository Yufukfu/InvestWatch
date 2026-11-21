# Proposal

**Stage 2 (etap 2).** This change depends on `analytics-worker` landing on `main` first. It is applied only after that change is merged, and its branch is rebased on it.

## Why

Analytics now routes only `firm_own` documents (to M2). Every `third_party` and `unknown` document is dropped with `module_not_implemented`, so the two UKNF questions about content published by someone else get no answer. Those questions are M1 (a finfluencer or another third party advertising a registered firm) and M3 (an entity outside the KNF registry offering what is in fact investment advice). Integration #2 (Sat 22:00) needs every module to produce findings from at least one source, and M1/M3 are the modules the scraper's social and web sources feed.

## What Changes

- **Routing** (`.docs/analytics-plan.md` §2 step 4): `third_party` and `unknown` documents go to M1 when the registry matches a firm, and to M3 when it does not. `firm_own` stays on M2. This replaces design decision 5 of the merged `analytics-skeleton`. A routed M3 document with no advisory signal produces no finding (log reason `no_signals`), so educational posts do not flood the dashboard. For third-party content, the registry match also looks at the hosts of the document's links, so a referral link to a firm's domain counts as a mention.
- **M1 signals S1.1-S1.6** (plan §4) as rules: registry match, affiliate or referral link and promo code, partnership label, call to action, author not equal to the firm. S1.5 (promotional vs educational) needs a model, so without one it is `uncertain` with no evidence.
- **M3 signals S3.1-S3.6** (plan §6) as rules: entity not in the registry, advisory-service vocabulary, paid model or signal subscription, targeting Poland. Personalization (S3.3) and recommendation of specific instruments (S3.4) need a model. Rules find candidate phrases and report them as `uncertain` until the LLM confirms or rejects them. S3.7 (KNF public warnings list) is in the catalogue as not implemented, and `advertiser.on_warning_list` stays `null`.
- **Scores**: M1 and M3 use `σ(bias + Σ wᵢ·xᵢ)`, with hand-tuned weights in YAML (plan §4). M3 adds the hard gate from plan §6: no S3.3 and no S3.4 caps the score at 0.4.
- **Findings** in the `Finding` v1 shape: `module` M1/M3, `firm` (M1 only), `advertiser`, and `rules` with S1.x/S3.x ids, a Polish title and summary, and the raw `score`. `Finding.advertiser` (`AdvertiserRef`) is added to the models by `analytics-worker` (its follow-up #3, from the `analytics-skeleton` follow-up #1). This change fills it. If the worker lands without it, this change adds it.
- **LLM seam**: this change uses the seam that the sibling stage-2 change `analytics-llm-p0` defines (its design §2): the shared `Rule`/`Catalogue`/`run_rules` engine, a YAML `llm:` block on S1.4, S1.5, S3.3 and S3.4, and the `judge` passed through `analyze`. The other signals have no `llm:` block, so the LLM never overrules them. Without a judge, or when it gives no verdict, M1/M3 stay rules-only with `model.llm = null`. This change does not build the LLM client, prompt, quote verification or cache; `analytics-llm-p0` does. The rules-only part (task groups 1-5) does not wait for it; wiring the judge into M1/M3 (group 6) starts after it is merged.
- **Tests** on the six M1/M3 mock documents in `contracts/mocks/documents.json` (ids `3c41441c…`, `182e5a42…`, `8721cb75…`, `007bbcee…`, `cdbf5306…`, `72acbb3b…`), checked against the signals in `contracts/mocks/findings.json` where rules alone can reach them.
- **Out of scope**: the LLM client, prompts and cache (`analytics-llm-p0`); the M2 P0 rules R4, R6, R10, R14, R17, R18 (`analytics-llm-p0`); the topic gate and embeddings (plan §2 step 2); the KNF public warnings list (S3.7) and the real KNF loader; the gold set, `eval/run.py` and calibration (plan §8); OCR of images; any change to the worker, storage or events code; `.docs/STATUS.md`, which the coordinator updates.
- **Owner**: Damian (`analytics/`).
- **Contracts**: reads `ScrapedDocument` v1 (`author`, `links`, `url`, `text`) and writes `Finding` v1 with `module` M1/M3, `advertiser` and S-ids. Both are allowed by `contracts/schemas/finding.schema.json` v1 as it is (`rule_id` pattern `S[13].[0-9]+`, `advertiser` object), so there is no contract change and no version bump. No REST route changes. Events are unchanged: the worker already publishes `finding.created` and `finding.high_risk` per module with the M1 0.6 / M3 0.7 thresholds (ADR 0305).

## Dependencies

- **`analytics-worker` (stage 1, unmerged):** must land first. It adds `AdvertiserRef` and the upsert on `(document_id, module)` that stores M1/M3 findings unchanged.
- **`analytics-llm-p0` (stage 2 sibling):** independent for the rules-only groups; task group 6 (LLM wiring for M1/M3) depends on it being merged. Both changes touch `rules/engine.py` (additive: per-module id check, `KNOWN_PARAMS`, here also `Rule.evidence_fields`) and `pipeline.py`, and both modify different requirements of `document-analysis`, so whichever lands second rebases and re-reads the main spec before archiving.

## Capabilities

### New Capabilities
- `m1-third-party-signals`: M1 signals S1.1-S1.6, their evidence, the M1 score and the M1 finding (firm, advertiser, content, URL).
- `m3-unauthorized-advice-signals`: M3 signals S3.1-S3.7, the hard gate, the M3 score and the M3 finding (entity data, offer content, URL).

### Modified Capabilities
- `document-analysis`: "Routing to modules" changes, because `third_party`/`unknown` now go to M1 or M3 by the registry result. Added requirements: registry match on link hosts for third-party content, the signal catalogue and its evidence sources, the advertiser on M1/M3 findings, and the LLM seam with rules-only degradation.

## Impact

- New code under `analytics/src/investwatch_analytics/`: `rules/m1.py`, `rules/m3.py`, `rules/m1_signals.yaml`, `rules/m3_signals.yaml`, `rules/scoring.py` (sigmoid score), `modules/m1.py`, `modules/m3.py`, `modules/advertiser.py`. Changed: `rules/engine.py` (per-module id check, `weight`/`bias`, new `KNOWN_PARAMS` keys, `Rule.evidence_fields`), `modules/router.py`, `pipeline.py`, `registry.py` (link-host match), `cli.py` (loads the signal catalogues). `rules/m2.py` and `m2_rules.yaml` stay untouched.
- Tests under `analytics/tests/` (`test_m1.py`, `test_m3.py`, `test_signal_catalogue.py`, `test_advertiser.py`, additions to `test_pipeline.py`, `test_registry.py`, `test_cli.py`).
- No new dependency.
- Docs: `analytics/README.md` (modules and signals), `.docs/analytics-plan.md` §2 (routing note), the AI log row. The skeleton's `firm_own` open question is answered or carried into this change's open questions.
