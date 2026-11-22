# Tasks

No test calls a real LLM (`stub_llm` only). Task 2.1 makes live calls; it is a measurement, not a test.

## 1. Bare results array (~30 min)

- [x] 1.1 Failing tests:
  - a bare array is accepted as `{"results": [...]}`, also after a `<thought>` block and inside a code fence;
  - an empty array is valid with no verdicts;
  - through the judge, an array answer with a quote in the document gives `fail` with that evidence, and a quote not in the document gives `uncertain`;
  - an invalid item in an array is dropped;
  - the string, number, boolean and null cases stay `LlmMalformed`, and so does an object without `results` (the old "array → malformed" case moves to the accepted cases).
- [x] 1.2 `ChatClient._content` turns a parsed list into `{"results": list}`; tests green
- [x] 1.3 Mutation check; `mutations: 5 tried, 5 caught`. On the first run, two survivors (wrapping any non-object, dropping the object guard) were closed by pinning the exception type and message for scalars. Two older tests that pinned 'array → malformed' (`test_llm_client.py::test_malformed`, `test_llm_judge.py::test_failures_degrade`) now use a JSON string instead, as the spec delta says

## 2. Evaluation (~30 min, mostly waiting)

- [x] 2.1 `eval/run.py --llm` with `gemma-4-26b-a4b-it` (`LLM_BREAKER_FAILURES=1000`), key never printed: the OK count of the calls and M1/M2/M3 P/R/F1 at the defaults, sent to the coordinator; defaults unchanged. 2026-11-22 01:03 UTC: 28 calls; 14 OK (5 before the fix), 12 returned 503, 2 timed out, 0 malformed (11 before). M1 n=18: P/R/F1 1.000/1.000/1.000, best 0.80, plateau [0.40, 0.80]. M2 n=35: 1.000/0.609/0.757, best 0.10. M3 n=18: 1.000/0.400/0.571, best 0.25. All four M3 calls failed (503 or timeout), so M3 equals rules-only and the result says nothing about the LLM's M3 verdicts

## 3. Closing

- [x] 3.1 Docs (`iw-docs-update`), the domain status file, `docs-check` clean
- [x] 3.2 AI log row (`iw-ai-log`)
- [x] 3.3 Final review (`iw-pr-review`): one `iw-reviewer` pass with `security: yes` over the whole change (it is a single group); no blocking findings
- [x] 3.4 Archive the change (last commit)

## Follow-ups

- S3.5 misses performance fees ("Prowizja od wyniku 20%"). In the #92 run the gold positive `m3-portfolio-management` lost its only offer signal once the LLM judged its S3.4 candidate `pass`, so it ended as `no_signals`. Add performance-fee phrasing to the S3.5 dictionary in a later change (coordinator: record it, don't do it now).
