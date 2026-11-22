# Follow-ups

| # | Item | Disposition |
|---|---|---|
| F1 | `contracts/mocks/findings.json` still has an M3 finding (0.22) for the mock `72acbb3b…` (the family-office explainer), and the pipeline now returns none for it (`no_signals`). The mocks are a read-only test double for `web/` and are not edited. | `docs`: the difference is recorded here; the mock stays an example of a capped M3 finding |
| F2 | LLM evaluation (task 4): with `gemma-4-26b-a4b-it`, 11 of 27 calls returned HTTP 200 with "message content is not a JSON object" (valid JSON that is not an object, most likely a bare `results` array), and `llm/client.py` rejects that by design. With 10 more 503s, only 5 calls succeeded, so the LLM numbers rest on about 4 documents. | `new-item`: a decision for Damian on whether to accept a top-level `results` array (an LLM-layer change, outside this change), then a re-run of `eval/run.py --llm` |
| F3 | The real defaults: the LLM run supports no change (M1 and M2 identical to rules-only; M3 recall 0.4 → 0.3 at 0.4 from one M3 verdict). The numbers went to the coordinator. | `wont-fix` here: Damian decides; this change leaves `eval/thresholds.json` and the defaults as committed |
| F4 | `tests/test_redos.py::test_catalogue_pattern_is_linear_on_adversarial_runs` failed twice under machine load on patterns this change does not touch (a different pattern each run, 0.09 s against a 0.057 s bound). | `wont-fix` here: the linked session `stabilize-flaky-redos-ti` owns that test |
