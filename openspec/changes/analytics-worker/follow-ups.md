# Follow-ups

Out-of-scope or deferred findings from reviews of this change. One disposition each.

| # | Source | Finding | Disposition |
|---|---|---|---|
| 1 | iw-reviewer, groups 1+3 | `publish_findings` catches only `redis.RedisError`; any other exception after the commit would escape. The spec says no exception escapes the worker loop. | fix-here (group 4: the loop wraps the publish call and logs anything else as `publish_failed` with the traceback) |
| 2 | iw-reviewer, groups 1+3 | A finding whose `document_id` has no row raises a plain `StoreError` in the in-memory store; Postgres raises an FK `IntegrityError`. Neither is `NotFound` or `StoreUnavailable`. | fix-here (group 2 maps the FK violation to the same `StoreError`; group 4 treats it as an unexpected error counted toward `MAX_DELIVERIES`) |
| 3 | iw-reviewer, groups 1+3 | `Finding` has no `advertiser`, so the upsert cannot replace it yet. | new-item (parent model from `analytics-skeleton`; add when M1/M3 produce advertisers) |
