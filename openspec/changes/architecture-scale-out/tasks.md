# Tasks

## 1. Run it first (evidence before any doc)

- [x] 1.1 Failing probe: write the scale probe in `infra/tests/smoke.sh` for two `analytics` and two `worker` replicas (running, distinct consumers in `XINFO CONSUMERS iw:documents analytics`); run it and confirm it fails or passes for the stated reason
- [x] 1.2 On a clean stack run `docker compose up -d --wait --scale worker=3 --scale analytics=2`; record `docker compose ps`, the consumer list, and one scan of several sources; note any error, duplicate findings row or lost entry
- [x] 1.3 Kill one `analytics` replica mid-batch and confirm another claims its pending entries; record `XPENDING`
- [x] 1.4 Read the analytics code paths shared across replicas (MinHash near-dup groups, `iw:stats:gate`, LLM cache) and check them against a two-replica run; open an issue for Damian for anything that duplicates or loses work
- [x] 1.5 Duplicate `scheduler` and `gateway` by mistake and record what happens
- [x] 1.6 Two `api` replicas through the gateway: try a browser Socket.IO session with the default transports; record whether the session survives and events arrive (the decision-2 gate)
- [x] 1.7 Mutation check; mutations: 3 tried, 3 caught (add a `container_name` to `worker`, then to `analytics`: the probe must go red)

## 2. Fix only what the run broke

- [x] 2.1 For each service claimed scalable that failed in group 1: failing test first, minimal fix in its compose file or, if the code is another owner's, an issue and a single-instance row instead (none failed: `worker` and `analytics` needed no fix)
- [x] 2.2 Only if 1.6 showed a cheap fix: gateway change for `api` replicas plus a probe for it, and an ADR in `.docs/decisions/` with the evidence; otherwise skip and record `api` as single-instance with the Socket.IO reason (1.6: the gateway sent every request to one replica, so no gateway change; `api` is single-instance)
- [x] 2.3 Mutation check for each fix (mutations: n/a, no fix was made)

## 3. Runbook

- [x] 3.1 `infra/README.md`: "Scale-out" section with the start, show and return commands, the table of every service (scalable / single-instance, one-line reason, evidence), and the LLM and politeness caveats; every service of `docker compose config --services` (with `llm`) appears once
- [x] 3.2 Record the resource sums of the scaled stack and hand them to issue #75 (comment)
- [x] 3.3 One before/after number on the same input set, or write "not measured"

## 4. Diagram and slides

- [ ] 4.1 `.docs/presentation-architecture.md`: slide 1 architecture diagram (services, networks, streams and channels, writes and reads, LLM variants), slide 2 scale-out table and demo commands, Notes and sources on each, "not claimed" list
- [ ] 4.2 Check the diagram against `docker compose config --services` and the networks in the compose files, and the stream and channel arrows against producers and consumers in the code; fix the diagram, not the check
- [ ] 4.3 One link from the root `README.md` to the runbook; no diagram there

## 5. Closing

- [ ] 5.1 Apply the `iw-docs-update` skill (docs, `.docs/status/dashboard.md`, `.docs/INDEX.md`, ADR if any), run `docs-check`, and add the `iw-ai-log` entry; comment on issue #74 with what was done and what stays open
- [ ] 5.2 Run the `iw-pr-review` skill and fix real findings
