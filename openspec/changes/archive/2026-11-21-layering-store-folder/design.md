# Design

Only the pattern list grows. `**/store/**` follows the existing `**/api/**` form. Known gaps are documented rather than patched: a `./data` sibling inside `components/` is not the data layer, alias and absolute paths do not exist in the repo yet, and a re-export through `model.ts` needs a rule on `model.ts` imports, which is a separate decision.
