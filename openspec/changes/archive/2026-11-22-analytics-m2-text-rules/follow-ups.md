# Follow-ups

| # | Source | Item | Disposition |
|---|---|---|---|
| F1 | review group 1 | R10 (like R4 and R6) treats a past-performance disclaimer as risk information. A Polish ad whose only risk warning is English, but which also has a Polish "wyniki historyczne nie są gwarancją…" sentence, therefore passes R10. | `wont-fix`: the same definition of a warning as R4 and R6 (one shared detector), and the spec does not say otherwise. It is a product call for Damian if the jury example needs it. |
| F2 | eval, group 2 | Adding R9 moves the rules-only best M2 threshold from 0.1 to 0.05 (F1 0.884 at 0.05 against 0.857 at 0.1), so `test_eval_thresholds` asserts 0.05 == 0.1. The R9 `uncertain` on `m2-r9-jargon-risk` lifts that positive above 0.05. | `fix-here`: Damian decided a rules-only R9 `uncertain` is not scored (design §5, `llm_only_uncertain`); the threshold stays 0.1 and `test_eval_thresholds` is green. |
| F3 | design | The R9 jargon list is short and Polish-only. | `new-item` if gold or live data show misses. |
| F4 | Damian, group 3 | `llm_only_uncertain` is available to any rule. Another LLM-first rule that has a weak rules signal could use it too. | `docs`: recorded in design §5; it applies only where a rule's rules-only `uncertain` carries no evidence. |
