# Follow-ups

Out-of-scope reviewer findings, "declined to judge" items and differences from the frozen mocks, one disposition each.

| # | Source | Item | Disposition |
|---|---|---|---|
| 1 | iw-reviewer, group 1 | `bias`/`weight` accepted `.nan` and `.inf` | `fix-here`: `_number` requires a finite value; cases in `test_malformed_signal_catalogue` |
| 2 | iw-reviewer, group 1 | S1.7 and S3.6 dictionaries are two copies in two files (a YAML anchor cannot cross files) | `fix-here`: the unused anchor is gone and `test_s17_and_s36_share_detection` keeps the copies equal |
| 3 | iw-reviewer, group 1 | Shipped-catalogue tests checked types only, not the weights or the `llm:` placement | `fix-here`: weights and bias pinned to design decision 10, `llm:` blocks pinned to S1.4, S1.5, S3.3, S3.4, integer YAML numbers cast to float |
| 4 | iw-reviewer, group 1, declined | An empty-string evidence passes the safety net (`"" in s`) | `wont-fix` for now: predates this change and no rule returns `""`; revisit if a rule ever builds evidence from a slice |
| 5 | iw-reviewer, group 1, declined | `generate_mocks.py` gives S1.5 severity `high` in one mock finding and `medium` in another; the catalogue uses `high` | `docs`: the mocks are a frozen test double (Damian's rule) and stay as they are; recorded here as a mock difference |
