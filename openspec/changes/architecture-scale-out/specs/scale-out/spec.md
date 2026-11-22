# Spec Delta

## Purpose
Say which InvestWatch services can run with more than one replica on one host, show it working, and keep the claim checked, so the "scalability" part of the architecture criterion rests on a run and not on a comment.

## ADDED Requirements

### Requirement: Scalable workers share one workload
`worker` (scraper) and `analytics` SHALL run correctly with several replicas started by `docker compose up -d --scale worker=<N> --scale analytics=<M>` from the root `compose.yaml`: no `container_name`, no published host port and no fixed address on either service, each replica a distinct consumer, and every unit of work (a scan job, a stream entry) handled by exactly one replica at a time.

#### Scenario: Replicas start and are healthy
- **WHEN** the stack is started with `--scale worker=3 --scale analytics=2`
- **THEN** three `worker` and two `analytics` containers are running, and `docker compose up --wait` exits 0

#### Scenario: Analytics replicas are separate consumers
- **WHEN** two `analytics` replicas run and documents are published on `iw:documents`
- **THEN** `XINFO CONSUMERS iw:documents analytics` lists two consumers with different names, and no document produces two findings rows for the same `(document_id, module)`

#### Scenario: A replica stops mid-work
- **WHEN** one `analytics` replica is killed while it holds unacknowledged entries
- **THEN** another replica claims them after the idle time and the document is analysed once, not lost and not duplicated

#### Scenario: Politeness holds across workers
- **WHEN** three `worker` replicas scan sources of one domain at the same time
- **THEN** request starts to that domain stay at least the configured interval apart and no more than the configured number of jobs for it run at once

### Requirement: Single-instance services are named and checked
The scale-out documentation SHALL list every service of the root stack as scalable or single-instance with the reason in one line, including `scheduler`, `seed`, `api-migrate`, `analytics-eval`, `postgres`, `redis`, `minio`, `ollama`, `gateway` and `web`. A service listed as single-instance SHALL either have no way to be duplicated by `--scale` (a published host port or a fixed name) or be shown to behave correctly when duplicated by mistake.

#### Scenario: Every service is classified
- **WHEN** the service names of `docker compose config --services` (with the `llm` profile) are compared with the table
- **THEN** each name appears in the table exactly once

#### Scenario: Scheduler duplicated by mistake
- **WHEN** `--scale scheduler=2` is used
- **THEN** a scan slot is enqueued once (unique job id per slot, ADR 0102) and no source is scanned twice for that slot

#### Scenario: Gateway cannot be duplicated
- **WHEN** `--scale gateway=2` is used
- **THEN** the second replica fails to start because the host port is taken, and the documentation says so

### Requirement: The api scales only if its realtime path does
`api` SHALL be documented as scalable only after a run with two replicas behind the gateway shows that the dashboard still receives `finding.*` events and keeps one Socket.IO session across HTTP long-polling requests and the upgrade. Otherwise it SHALL be documented as single-instance with that reason.

#### Scenario: Two api replicas, one browser session
- **WHEN** two `api` replicas run and a browser connects to `/socket.io` through the gateway
- **THEN** either every request of the session reaches the same replica and an event published on `iw:events` arrives in the browser, or `api` is listed as single-instance in the table

#### Scenario: Event reaches every connected client
- **WHEN** two `api` replicas each hold one connected client and an event is published once on `iw:events`
- **THEN** both clients receive it once

### Requirement: Scale-out is observable in the demo
The runbook SHALL give the commands to start the scaled stack, to show the replicas and their share of the work, and to return to one replica of each, and SHALL report only numbers it measured, with the machine and date.

#### Scenario: Show the replicas
- **WHEN** the runbook commands are run on a scaled stack
- **THEN** they print the replica count per service and the per-consumer pending and processed counts of `iw:documents`

#### Scenario: Measured claim or no claim
- **WHEN** the slide states a speed-up or a throughput
- **THEN** the number comes from a recorded run with replicas and the same run with one replica, on the same machine, and its command is in the notes

### Requirement: The scale claim is rechecked by the smoke test
`infra/tests/smoke.sh` SHALL include a check that starts two `analytics` or `worker` replicas on a throwaway project, confirms both are running and, for `analytics`, that both are consumers of the group, and tears them down.

#### Scenario: Probe passes on the committed stack
- **WHEN** `infra/tests/smoke.sh` runs on `main`
- **THEN** the scale probe passes

#### Scenario: Probe fails on a fixed name
- **WHEN** a `container_name` is added to `analytics` or `worker`
- **THEN** the scale probe fails
