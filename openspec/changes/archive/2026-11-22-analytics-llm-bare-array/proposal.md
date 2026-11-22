# Proposal

## Why

The LLM evaluation in `analytics-post-integration-fixes` (PR #92) ran hosted `gemma-4-26b-a4b-it`, the model Damian's `.env` now uses. 11 of its 27 answers were HTTP 200 with valid JSON that `llm/client.py` rejected as "message content is not a JSON object". So every LLM verdict of those modules was dropped. That is the largest LLM loss after the provider's 503s.

A debug run on 2026-11-22 saved the message content of each reply: only the content, never the request, headers or key. Of 8 M1 gold-set replies, 5 were bare arrays `[{"rule_id", "result", "evidence_quote", "explanation"}, …]` with exactly the item keys of the prompt's schema, and 3 were `{"results": [...]}`. The model follows the item schema and only drops the wrapper object. Damian decided (via the coordinator, follow-up F2 of #92) to accept the bare array.

## What Changes

- `llm/client.py` `ChatClient._content`: when the parsed content (after the existing `<thought>` and code-fence stripping) is a JSON array, the client returns `{"results": <array>}`. The judge, the per-item Pydantic validation, the quote verification and the cache then see the same shape as for an object answer, so nothing becomes less strict.
- Content that is valid JSON but neither an object nor an array (a string, number, boolean or null) stays `LlmMalformed`, and so does an object without a `results` list.
- **Tests:** the existing malformed-case test that pinned "array → malformed" moves to the accepted cases, as the spec delta says. New cases cover the array with a `<thought>` block, in a code fence, empty, with an invalid item, and through the judge with quote verification.
- **Evaluation:** one re-run of `eval/run.py --llm` with `gemma-4-26b-a4b-it`, reporting the OK count and M1/M2/M3 P/R/F1 to the coordinator. **The defaults do not change.**

## Out of scope

- The prompt itself (it still asks for the object), retries on 503, and the defaults.
- `pipeline.py`, the rules, the mocks and the other modules.
- **Owner:** Damian (`analytics/`).
- **Contracts:** none. No contract, REST route or event changes. It touches only the LLM response handling inside analytics.
- **Base:** this branch stacks on `analytics/analytics-post-integration-fixes` (PR #92, not merged yet). Its PR targets `main` once #92 merges.
