---
when: Sun 04:59
who: Damian
---

## What was done with AI

A Claude Code session started by the coordinator measured DeepSeek Flash as the hosted LLM. It ran:
- a smoke test of the OpenAI-compatible API;
- the gold-set evaluation rules-only and with `--llm`;
- an end-to-end run on the `iw-latest` stack: demo sources, cache second pass, and the rules-only fallback with an invalid key.

DeepSeek returned plain JSON objects with our request shape. 119 of 120 calls were valid, at 3.1 s per call on the gold set and 6.7 s on real pages, so the client needed no change.

On Damian's decision, the same session made DeepSeek Flash the hosted default and set M1's default threshold to 0.75 from the DeepSeek run (ADR 0318). It committed that run as `analytics/eval/llm-run-deepseek-flash.json`, so the tests can check the value against it.

## Outcome / lesson

The test written first assumed 0.75 was the recommended threshold. It failed, because ADR 0316's tie rule takes the higher end of the plateau, 0.8, and 0.75 is the lower end. Both give the same counts on the gold set. The code now records 0.75 as Damian's choice and checks only that it lies on the recorded run's plateau, and the ADR says where it departs from 0316.

An LLM-measured default cannot be re-measured in tests, which never call a real LLM. So the tests pin the recorded run to the gold set's sha256 and to M1's rules-only default. A gold or rule change then fails until someone re-runs `--llm`.

A mutation check (M1 0.7, a wrong gold sha) confirmed the new tests fail.
