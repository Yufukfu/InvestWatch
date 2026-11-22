# architecture-overview Specification

## Purpose

One diagram and its slides that show how InvestWatch is composed, so the jury can read module boundaries, data flow and network isolation at a glance and trust that they match what `docker compose up` starts.

## Requirements

### Requirement: Diagram equals the stack
The architecture diagram SHALL show every service started by the root `compose.yaml` (default profile) and the optional `ollama` profile, the three networks `edge`, `data` and `egress` with which services sit on each, the Redis stream `iw:documents`, the pub/sub channel `iw:events` and the scan-request stream, the Postgres and object-storage writes and reads per module, and the LLM endpoint with its hosted and local variants. Names SHALL be those in the compose files.

#### Scenario: No missing service
- **WHEN** the service names from `docker compose config --services` (with the `llm` profile) are compared with the diagram
- **THEN** every name appears in the diagram, or the slide notes say why a one-shot (`api-migrate`, `minio-init`, `seed`, `analytics-eval`, `ollama-pull`) is drawn as a note

#### Scenario: Networks match
- **WHEN** the networks of a service in the diagram are compared with its `networks:` in the compose files
- **THEN** they are equal, and only `gateway` is drawn with a host port

#### Scenario: Flows match the code
- **WHEN** an arrow for a stream or channel is compared with the producer and consumer in the code
- **THEN** the producer and consumer named on the arrow publish and read that key, and the iw:scan-requests arrow goes from `api` to the scraper

### Requirement: Architecture slides in the hand-in format
`.docs/presentation-architecture.md` SHALL hold two slides in the format of the other presentation files (one `##` per slide, a **Notes** paragraph, every number sourced): the architecture diagram with the module boundaries and network isolation, and the scale-out slide with the scalable/single-instance table and the demo commands. It SHALL name what is not claimed.

#### Scenario: Slides are self-contained
- **WHEN** Kacper pastes the file into the deck
- **THEN** each slide has its figure or table, its notes and the sources of its numbers, with no TODO

#### Scenario: Honest limits stated
- **WHEN** a service was not run with more than one replica
- **THEN** the slide does not call it scalable

### Requirement: README stays minimal
The root `README.md` SHALL gain at most one link to the diagram and the scale-out runbook, and no embedded diagram, unless the team asks for one in issue #74.

#### Scenario: Link only
- **WHEN** the root README is diffed against `main`
- **THEN** the change is at most one line pointing to the runbook
