# event-relay Specification

## Purpose
Deliver real-time events to the dashboard: every valid event on Redis Pub/Sub `iw:events` reaches Socket.IO clients on namespace `/events`, unchanged and without threshold logic (ADR 0305). Owned by `api/`.
## Requirements
### Requirement: Relay iw:events to Socket.IO
The API SHALL subscribe to Redis Pub/Sub channel `iw:events` and, for each message that validates against the `event` definition of `contracts/schemas/events.schema.json`, emit a Socket.IO event on namespace `/events` (path `/socket.io`) whose name is the message `type` and whose payload is the message `data`, unchanged.

#### Scenario: Finding created
- **WHEN** analytics publishes `{"type": "finding.created", "emitted_at": "...", "data": {id, module, score, title, url, platform}}` on `iw:events`
- **THEN** every client connected to `/events` receives a `finding.created` event with exactly that `data`

#### Scenario: High-risk alert passes through
- **WHEN** analytics publishes a `finding.high_risk` event
- **THEN** clients receive `finding.high_risk` with the same `data`, and the API does not re-check the score against any threshold

#### Scenario: Scan progress
- **WHEN** the scraper publishes `scan.started` and then `scan.finished` for one source
- **THEN** clients receive them in that order

#### Scenario: No client connected
- **WHEN** an event is published while no client is connected
- **THEN** it is dropped without error (Pub/Sub has no replay; the dashboard refetches over REST on connect)

### Requirement: Invalid messages are dropped
The relay SHALL drop, and log as a warning with the reason and the event `type` if readable, any message on `iw:events` that is not JSON or does not validate against the event schema, and SHALL keep relaying later messages.

#### Scenario: Not JSON
- **WHEN** the text `hello` is published on `iw:events`
- **THEN** no Socket.IO event is emitted, a warning is logged, and the next valid event is still delivered

#### Scenario: Unknown type
- **WHEN** `{"type": "finding.deleted", "emitted_at": "...", "data": {}}` is published
- **THEN** it is not emitted

#### Scenario: Payload not matching its type
- **WHEN** a `finding.updated` event is published with `data` missing `status`
- **THEN** it is not emitted

### Requirement: API publishes its own events on the same channel
Events the API produces (`finding.updated` after a `PATCH /api/findings/{id}`) SHALL be published on `iw:events` in the contract shape with `emitted_at` in UTC, and reach clients through the same relay, so that several API instances deliver them to all clients.

#### Scenario: Status change reaches another tab
- **WHEN** client A patches a finding's status and client B is connected to `/events`
- **THEN** client B receives one `finding.updated` event `{id, status}` with the new status

### Requirement: Relay survives Redis outages
When the Redis connection drops, the relay SHALL reconnect with a capped backoff (at most 10 seconds between attempts) and resume relaying, and `/api/health` SHALL report `redis` as `down` while it is disconnected. Socket.IO clients SHALL stay connected during the outage.

#### Scenario: Redis restarts
- **WHEN** Redis is restarted while a client is connected
- **THEN** the client stays connected, `/api/health` shows `redis: "down"` during the outage, and an event published after Redis is back is delivered

#### Scenario: Redis down at start-up
- **WHEN** the API starts while Redis is unreachable
- **THEN** the REST routes that do not need Redis still answer, and the relay starts delivering once Redis is reachable

### Requirement: Socket.IO reachable through the gateway
The Socket.IO server SHALL accept connections on path `/socket.io` behind the Caddy gateway (same origin as the dashboard), and SHALL accept cross-origin connections only from the origins listed in env `CORS_ORIGINS` (empty by default).

#### Scenario: Same-origin connection
- **WHEN** the dashboard served at `https://localhost:8443` connects to `/events`
- **THEN** the WebSocket connection is established through the gateway

#### Scenario: Foreign origin rejected
- **WHEN** a page from an origin not in `CORS_ORIGINS` tries to connect
- **THEN** the connection is refused

