# Follow-ups

Out-of-scope or deferred findings from reviews of this change. One disposition each.

| # | Source | Finding | Disposition |
|---|---|---|---|
| 1 | iw-reviewer, groups 1+3 | `publish_findings` catches only `redis.RedisError`; any other exception after the commit would escape. The spec says no exception escapes the worker loop. | fixed in group 4: the worker wraps the publish call and logs anything else as `publish_failed` with the traceback (`test_non_redis_publish_error_is_logged_and_acked`) |
| 2 | iw-reviewer, groups 1+3 | A finding whose `document_id` has no row raises a plain `StoreError` in the in-memory store; Postgres raises an FK `IntegrityError`. Neither is `NotFound` or `StoreUnavailable`. | fixed: group 2 maps every non-connection driver error to a detail-free `StoreError`; group 4 counts it toward `MAX_DELIVERIES` (`test_unexpected_store_error_counts_toward_max_deliveries`); a malformed `DATABASE_URL` (`StoreMisconfigured`) exits with code 2 instead of retrying |
| 3 | iw-reviewer, groups 1+3 | `Finding` has no `advertiser`, so the upsert cannot replace it yet. | new-item (parent model from `analytics-skeleton`; add when M1/M3 produce advertisers) |
