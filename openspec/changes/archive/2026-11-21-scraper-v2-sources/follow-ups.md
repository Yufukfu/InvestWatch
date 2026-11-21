# Follow-ups

Findings of the `iw-reviewer` passes on group 1 (`66b3c40..8e2d46d`) and on the whole branch (`66b3c40..0bb323e`) and their declined-to-judge lists. Fixed findings are in the follow-up commits and not repeated here.

| Item | Disposition | Note |
|---|---|---|
| The publisher classification of each seeded page (`firm_own`, `third_party`, `unknown`) is a factual claim about who publishes it | docs | An agent cannot check it against the KNF registry. The PR body asks a human to read the 12 rows; `sources.toml` carries a comment per row. |
| The 12 URLs were researched in an earlier session, not verified on this branch | fix-here | Done: the live check (`scraper/tests/test_seed_live.py`) passed for all 12 pages after the human's go-ahead; its output is in the PR body. |
| `ENTRIES = load_seed_dir(SEEDS_DIR)` runs at collection in `test_seed.py` and `test_seed_live.py`, so a broken seed file breaks collection of the whole suite | wont-fix | Fail-fast is the point: a seed file that does not validate must stop CI, not hide behind a skipped test. |
| No test names "a `third_party` row is a ranking or review page" | wont-fix | It is a classification, not behaviour; the human read in the first row covers it. |
| `seed_knf` keeps the old `$2`-twice SQL without casts | wont-fix | Parameterised, tested against PostgreSQL, and its row layout is `scraper-orchestration`'s code. |
| The second report line of `python -m iw_scraper.seed` (`sources: inserted N, already present M`) is new | docs | Nothing in compose or CI parses the output (searched `infra/`, `compose.yaml`, `.github/`); it is in the PR body as a behaviour change. |
| `seed_knf` stores the optional `CRON` argument of the command line without validating it | wont-fix | Predates this change (`scraper-orchestration`, PR 38) and applies to the KNF row only; the seed files' crons are validated, and the dashboard owns later edits. |
| Cron staggering of the seeded rows against the orchestration limits was not judged | wont-fix | It follows design.md decision 9 and PR 38's per-domain cap; the demo triggers scans by hand. |
| PR 43 review: a seed file of another platform (`telegram.toml`) broke the web-path tests | fix-here | Done: `test_seed.py` (guard test) and `test_seed_live.py` keep only `platform == "web"` rows; reproduced with a probe `telegram.toml`, 1 failed before and 64 passed after. |
| PR 43 review: a wrong TOML type (`platform = ["web"]`, `source_kind = {a=1}`, `target_modules = [["M3"]]`) raised a bare `TypeError` | fix-here | Done: `isinstance` checks before the membership tests; `mutations: 7 tried, 7 caught` (shared with the URL fix on the next row). |
| PR 43 review: the URL check accepted control characters and ports other than 443 | fix-here | Done: `isprintable()` and `parts.port in (None, 443)` (a bad port raises ValueError, reported with file and entry); same 7 mutants. |
| PR 43 review: refuse an IP-literal or single-label host in the seed check | wont-fix | `AddressGuard.check` already refuses both at fetch time (`_require_public` for a literal, `"." not in name` for a bare name), and the stored row only fails its own runs as `blocked_target`; the diff stays small. |
| PR 43 review: validation ran inside the database `try`, so a wrong `CONTRACTS_DIR` was reported as a database failure | fix-here | Done: `main` loads `load_seed_dir(SEEDS_DIR)` before `create_pool` and passes the entries to `seed_all`; an unreadable contract schema is a `SeedError` naming the path; the schema is read once per load; `mutations: 7 tried, 6 caught` (the survivor, reading the files a second time inside `seed_all`'s call, only repeats a validation that already passed). |
