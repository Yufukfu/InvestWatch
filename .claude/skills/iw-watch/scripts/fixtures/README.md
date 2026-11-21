# Fixtures

Saved `gh` output from this repository on 2026-11-21, trimmed (bodies cut to 200 characters, file lists shortened):

- `pr-11.json`, `reviews-11.json`, `review-comments-11.json`: `gh pr view 11 --json ...` and `gh api repos/Yufukfu/InvestWatch/pulls/11/{reviews,comments}` (Adam's review on Kacper's PR).
- `pr-28.json`: `gh pr view 28 --json ...` (Damian's PR), used as a review request.
- `pr-list-mine.json`, `reviews-27.json`: PR 27 and its reviews.
- `pr-comments.json`: the shape of `gh api repos/.../issues/27/comments`; the `<!-- iw-watch -->` markers and the last two entries are added for the round-count tests.
- `checks-failed.json`: written by hand in the shape of `statusCheckRollup` (CheckRun and StatusContext), since no PR here had a failing check when the fixtures were saved.
