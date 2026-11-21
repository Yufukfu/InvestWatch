# Design

## Context

Stateless Python async workers that run collections from a queue, on a schedule and on request, and scale by replica count. Fetching and parsing are `scraper-v1`; storage and announcement are `scraper-ingest`. Scope: `proposal.md`.

## Goals / Non-Goals

**Goals:** horizontal scale and stability without coordination code (all shared state in Redis or PostgreSQL); a dashboard progress bar that never hangs.

**Non-Goals:** social collectors, Playwright rendering, crawling beyond one URL per run.

## Decisions

- **Terms.** Job = one enqueued unit for a source; attempt = one execution of it by the queue (retries make several); run = the fetching of one attempt; session = the state of one run. The run lock and `scan.*` events belong to the job; sessions and identities belong to the attempt; the domain failure count is per job final outcome.
- **Queue and scheduler**: `arq` on Redis (ADR 0102). The queue is the only place that retries (`timeout` and 5xx, capped, backoff with jitter, `Retry-After` can raise a delay, never shorten it). `schedule_cron` strings are parsed by us. Each due job gets a unique id per source and cron slot, so replicas never double-enqueue.
- **Shared state in Redis**: a per-domain *concurrency cap* (counting semaphore with expiring leases) on jobs running at once. Spacing request starts (a token-bucket rate limit) is not built here: it belongs to the fetch layer in `scraper-v1`. Also `Retry-After` deferral, a per-domain failure cooldown (consecutive failed jobs) and a per-source run lock held for the whole job and renewed while it lives. Stale leases and locks expire, so a crash cannot make a source unrunnable. A job that meets a deferral, a paused domain or an all-proxies-cooling state is requeued with a delay: not a failure, no retry consumed, no event.
- **Scan requests** go through a consumer group with a stable consumer name per worker and a periodic claim of messages pending too long. The consumer only enqueues; the job does the work, so there is one code path. A refused request with a valid `source_id` publishes `scan.finished` with `status: failed`, so the dashboard progress bar never hangs. `scan.*` fire once per job, not per retry. A requested job that ends without running (source deactivated after enqueue) publishes `scan.finished` failed; a scheduled one stays silent; a coalesced one is silent because the running job covers the source.
- **Scheduler and worker process layout**: the integration plan lists a `scheduler` service; here it is the same image run with a different command (`arq` worker vs cron enqueuer), both stateless. The `/health` endpoint runs in the worker (it also holds the consumer); the scheduler has none and is restarted by the compose restart policy.
- **Deferrals are requeues.** A run that reports a deferral (`scraper-v1` returns the time it ends) is requeued with a delay: not a failure, no retry consumed, no event. The queue records one outcome per job, at its final outcome, into the domain failure cooldown.

## Risks / Trade-offs

- [Redis down] -> the supervisors reconnect with backoff, the worker stays up and `/health` reports 503 naming Redis.
- [`arq` duplicate-job-id behaviour] -> verified (a duplicate id returns `None`, `test_scheduler.py`); see ADR 0102.
- [`arq` resume after restart] -> verified (queued jobs survive a killed worker, `test_concurrency_cap.py`); see ADR 0102.

## Open Questions

- None blocking.
