# Follow-ups

Findings of the `iw-reviewer` passes on group 1 (`66b3c40..8e2d46d`) and on the whole branch (`66b3c40..0bb323e`) and their declined-to-judge lists. Fixed findings are in the follow-up commits and not repeated here.

| Item | Disposition | Note |
|---|---|---|
| The publisher classification of each seeded page (`firm_own`, `third_party`, `unknown`) is a factual claim about who publishes it | docs | An agent cannot check it against the KNF registry. The PR body asks a human to read the 12 rows; `sources.toml` carries a comment per row. |
| The 12 URLs were researched in an earlier session, not verified on this branch | fix-here | The live check (`scraper/tests/test_seed_live.py`) is the proof. It needs a human go-ahead; task 2.2 stays open until it has run and its output is in the PR body. |
| `ENTRIES = load_seed_dir(SEEDS_DIR)` runs at collection in `test_seed.py` and `test_seed_live.py`, so a broken seed file breaks collection of the whole suite | wont-fix | Fail-fast is the point: a seed file that does not validate must stop CI, not hide behind a skipped test. |
| No test names "a `third_party` row is a ranking or review page" | wont-fix | It is a classification, not behaviour; the human read in the first row covers it. |
| `seed_knf` keeps the old `$2`-twice SQL without casts | wont-fix | Parameterised, tested against PostgreSQL, and its row layout is `scraper-orchestration`'s code. |
| The second report line of `python -m iw_scraper.seed` (`sources: inserted N, already present M`) is new | docs | Nothing in compose or CI parses the output (searched `infra/`, `compose.yaml`, `.github/`); it is in the PR body as a behaviour change. |
| Cron staggering of the seeded rows against the orchestration limits was not judged | wont-fix | It follows design.md decision 9 and PR 38's per-domain cap; the demo triggers scans by hand. |
