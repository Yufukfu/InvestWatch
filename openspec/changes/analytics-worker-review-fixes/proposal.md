# Proposal

## Why

Kacper's review of PR #26 (`analytics-worker`, review of 225e9cf) found no blocking code defect but asked for honesty and hygiene fixes before merge. The main ones: the shipped container judges real firms against 3 fictional ones, a plan line still promises URL-level dedup, the security audit has no worker entry, and the worker joins `egress` though it makes no outbound call. The coordinating session decided how to handle each item. This change applies those decisions to the branch of PR #26.

## What Changes

- **Registry honesty:** when the worker starts with the bundled fictional `registry/seed.csv`, it logs a WARNING (`reason: registry_seed`) saying that R1 results and high-risk alerts for real firms are not meaningful until a real KNF registry is loaded through `REGISTRY_CSV`. `analytics/compose.yaml` comments the same next to a `REGISTRY_CSV` slot, and `analytics/README.md` and `.docs/status/platform.md` say it plainly. R1 semantics do not change.
- **Clean-page title:** the M2 title of a finding with no fail and no uncertain result names the rules it checked ("brak naruszeń w regułach R1, R2, R3"), instead of "brak naruszeń w sprawdzonych regułach", so a clean card cannot be read as a full UKNF check.
- **Compose:** the `analytics` service joins only infra's `data` network. `egress` comes back with the LLM client (`analytics-llm-p0`). The empty `LLM_*` env slots stay.
- **Test helpers out of the service:** `InMemoryStore` and `NoopPublisher` move to `investwatch_analytics/testing.py`, which `worker.main` never imports. The production modules keep only the interfaces and the Postgres and Redis implementations. `worker.main` reads `Settings.from_env(env)` (which gains an optional mapping) instead of its own copy and the private `config._DEFAULT_REGISTRY`.
- **Tests run in CI:** the Postgres store tests also accept `TEST_DATABASE_ADMIN_URL`, and the real-Redis test also accepts `IW_TEST_REDIS_URL`. These are the test-only variables CI (#24) already sets, so CI runs them instead of skipping. They still run on the hand-copied `tests/sql/schema.sql`. A one-time structural comparison with the real migrations 0001-0003 is recorded, and an automated comparison is a follow-up.
- **Hostile text stays linear (Kacper's second review, required item 4):** the sentence splitter's boundary regex re-scanned whitespace runs on every backtrack (". " + 40 000 spaces took ~15 s), its abbreviation check re-scanned the growing sentence prefix (an `S.A. Ab` chain took ~10 s), R3's percent pattern `\d+(?:[.,]\d+)?\s?%` was quadratic on a digit run (40 000 digits took ~130 s), its fee exclusion on one long word of repeated stems, and R3's claim-to-warning coverage compared every claim with every warning ("Zysk 5%. Ryzyko straty." x 16 000 took ~65 s). All are linear now (possessive whitespace with a bounded marker gap, a 16-character abbreviation window, digit runs matched from their first digit only, the same `(?<!\d)` edit as `analytics-llm-p0` 9660ab4, a `` on the fee exclusion, coverage by `bisect`); the splitter's output is unchanged on 20 009 sample texts.
- **Docs:** fix `.docs/analytics-plan.md` §4 (re-analysis of the same document updates its finding; a changed page is a new document with a new finding, key `(document_id, module)`). Add a worker entry and a fresh `pip-audit` row to `.docs/security-audit.md`, fix the stale "proposed, awaiting approval" line in `.docs/status/platform.md`, add a `.docs/INDEX.md` router row for operating the worker, and add the follow-ups.
- Out of scope: a real KNF registry loader, URL-level grouping, events for threshold crossings on re-analysis, and an automated schema-drift test. Each is recorded in `follow-ups.md` with a disposition.
- Owner: Damian (`analytics/`). Contracts: none touched. No REST route or event changes. The worker's log gains one startup line.

## Capabilities

### New Capabilities

### Modified Capabilities
- `document-analysis`: preprocessing and the rules-only checks run in linear time on hostile text.
- `document-stream-worker`: a startup warning for the bundled registry; the container joins `data` only.

## Impact

- `analytics/src/investwatch_analytics/{worker,storage,events,config,testing}.py`, `modules/m2.py` (title only), the tests, `analytics/compose.yaml`, `analytics/README.md`, `analytics/.env.example`.
- Docs: `.docs/analytics-plan.md`, `.docs/security-audit.md`, `.docs/status/platform.md`, `.docs/INDEX.md`, the AI log row.
- No dependency changes.
