# Tasks

No test calls a real LLM (`stub_llm` only). Task 2.1 makes live calls; it is a measurement, not a test.

## 1. Bare results array (~30 min)

- [ ] 1.1 Failing tests:
  - a bare array is accepted as `{"results": [...]}`, also after a `<thought>` block and inside a code fence;
  - an empty array is valid with no verdicts;
  - through the judge, an array answer with a quote in the document gives `fail` with that evidence, and a quote not in the document gives `uncertain`;
  - an invalid item in an array is dropped;
  - the string, number, boolean and null cases stay `LlmMalformed`, and so does an object without `results` (the old "array → malformed" case moves to the accepted cases).
- [ ] 1.2 `ChatClient._content` turns a parsed list into `{"results": list}`; tests green
- [ ] 1.3 Mutation check

## 2. Evaluation (~30 min, mostly waiting)

- [ ] 2.1 `eval/run.py --llm` with `gemma-4-26b-a4b-it` (`LLM_BREAKER_FAILURES=1000`), key never printed: the OK count of the calls and M1/M2/M3 P/R/F1 at the defaults, sent to the coordinator; defaults unchanged

## 3. Closing

- [ ] 3.1 Docs (`iw-docs-update`), the domain status file, `docs-check` clean
- [ ] 3.2 AI log row (`iw-ai-log`)
- [ ] 3.3 Final review (`iw-pr-review`)
- [ ] 3.4 Archive the change (last commit)
