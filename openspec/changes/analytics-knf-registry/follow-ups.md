# Follow-ups

Out-of-scope or deferred findings from reviews of this change. One disposition each.

| # | Source | Finding | Disposition |
|---|---|---|---|
| 1 | iw-reviewer, group 1 | `urlopen` followed redirects to any host or scheme, so a redirect could make another site's HTML the register | fixed in the group 1 review commit: `KnfOnlyRedirects` refuses any target off `https://www.knf.gov.pl/` (`test_redirect_off_the_knf_host_is_refused`, `test_default_opener_refuses_foreign_redirects`) |
| 2 | iw-reviewer, group 1 | Records were deduplicated by full text, so identical duplicates on different pages were dropped silently | fixed: the list ends when a page repeats the previous page; every record is kept and merged in `build.py` (`test_identical_records_on_two_pages_are_both_kept`) |
| 3 | iw-reviewer, group 1 | The 100-page cap failed a list of exactly 100 pages | fixed: page `max_pages + 1` is fetched as the expected repeat (`test_exactly_max_pages_is_allowed`) |
| 4 | iw-reviewer, group 1 | Task 1.1 promised a `?page=99` snapshot and an empty-list fixture | fixed: the task text names the snapshots that exist (the `?page=99` answer equals page 36, recorded in the fixtures README and `evidence.md`); the empty list is a test (`test_empty_list_yields_no_records_here`); its `count_dropped` failure is group 5 |
| 5 | iw-reviewer, group 1 | No response size limit; the `HTTPError` body was never closed | fixed: 5 MB limit, not retried (`test_oversized_response_fails`); the error response is closed |
| 6 | iw-reviewer, group 1 | No test pinned the 2 req/s default | fixed (`test_defaults_are_two_requests_per_second_three_attempts_and_a_timeout`) |
| 7 | iw-reviewer, group 1 | A nested `<table>` inside a record would reset that record's fields | wont-fix: the real markup has none; a layout change of that kind shows as missing labels or counts |
| 8 | iw-reviewer, group 1 | `<s>` and `<del>` are not treated as strike-through | wont-fix: KNF uses only `<strike>` (`evidence.md`); a switch would show up as former names appearing as current lines in the refresh summary |
