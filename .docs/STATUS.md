# Status

Team-wide state only: milestones and decisions that need the whole team. Module state, active OpenSpec changes and module blockers live in one file per domain (below); whoever changes a directory updates only the file that covers it, which limits merge conflicts ([ADR 0205](decisions/0205-status-per-domain.md), [ADR 0211](decisions/0211-codeowners-single-source.md)). Agents read this file and then the file for the directories they change at session start. The owner of a milestone edits its row here.

## Milestones (from `integration-plan.md` §8)

| When | Milestone | State |
|---|---|---|
| Sat 14:30 | Contracts v1 frozen, compose infra up | contracts: required core frozen, optional fields provisional until Sat 17:00 ([ADR 0301](decisions/0301-contracts-v1.md), accepted); compose infra: Postgres + HTTPS gateway up (Kacper, PR #6); Redis, object storage (MinIO, bucket `iw-raw`) and the optional Ollama profile `llm` in PR #18 (`infra-compose`, Damian) |
| Sat 17:00 | Integration #1: one real document, end to end | analytics + api verified on a clean stack from `main` c810a14 (#78, 2026-11-22): scan request → scraper → `iw:documents` → analytics → `findings` + `iw:events` → `GET /api/findings` through the gateway. Dashboard part (Kacper) and scraper part (Adam) pending a rerun in #78. Scraper part (Adam, from the recorded run and code, no rerun): 17 seeded sources (13 web, 4 Telegram), 17 manual scan requests (all 202), documents from all 17 sources, 0 `job_errors` ([status/scraper.md](status/scraper.md), "Demo rehearsal") |
| Sat 22:00 | Integration #2: all modules, one source each | analytics: M1, M2 and M3 all fire on real seeded sources (#78): 223 documents from 17 sources, 72 findings (M1 54, M2 5, M3 13), 10 `finding.high_risk` events, 0 analytics errors. Gaps: hosted LLM unavailable (1 of 5 calls OK, then breaker, 71 of 72 findings rules-only); one negative control (Grant Thornton) is high-risk M3 0.78 because S3.4 stays `uncertain` without the LLM. Scraper: all 17 sources scraped in one run, 223 documents (13 web pages, 210 from 4 Telegram channels by difference); no `blocks` or screenshots, because the renderer (PR #67) merged after the run and is off by default |
| Sun 03:00 | Integration #3: calibration, scheduled scans | analytics: `analytics-eval` stores the gold-set run on `up`, `GET /api/calibration` returns the curve per module through the gateway (#78). Moving the threshold in the dashboard and scheduled scans not checked by analytics. Scraper: scheduled scans not checked (the run used manual scan requests only; `scheduler` logs not recorded) |
| Sun 08:00 | Feature freeze | upcoming when this was written (Sun, about 06:00); `main` at `313c625b`; the one open feature PR is #159 (M2 R5, R7, R8, R13, conflicting with `main`), so it is not claimed anywhere |
| Sun 10:30 | Hand-in | in preparation: title, PL/EN description, slide sources and order are in [hand-in.md](hand-in.md); the PDF, the optional video and the form are the human's (checklist there) |

## Domain status

| File | Covers |
|---|---|
| [status/scraper.md](status/scraper.md) | `scraper/` |
| [status/dashboard.md](status/dashboard.md) | `web/`, `infra/` |
| [status/platform.md](status/platform.md) | `analytics/`, `api/`, `contracts/` |

Whoever changes a directory updates the file that covers it. Who owns a directory is in [`.github/CODEOWNERS`](../.github/CODEOWNERS) only ([ADR 0211](decisions/0211-codeowners-single-source.md)). A blocker goes in the file of the domain it blocks.

## Team-wide blockers and open decisions

- Repository layout (`scraper/`, `analytics/`, `web/`, `contracts/`, `api/`, `infra/`, `.docs/`, `doc/` for UKNF materials): a new top-level directory needs the whole team's OK ([ADR 0211](decisions/0211-codeowners-single-source.md)).
- Demo path: resolved. The `api` is in the root compose, so `docker compose up` runs the whole system and the first run scans the seeded sources ([first-run bootstrap](../openspec/specs/first-run-bootstrap/spec.md)); the dashboard still has the contract mock server (`contracts/mock-server`) for development without the backend ([ADR 0206](decisions/0206-dashboard-data-from-backend.md)). Open: the dashboard clicked through on real seeded data is not recorded yet ([hand-in.md](hand-in.md) checklist).
- Dependency and secret scans: results go in each PR body ("Security scans" section), not in a shared file; `.docs/security-audit.md` keeps service notes and the hand-in run ([ADR 0209](decisions/0209-supply-chain-scanning.md), [integration-plan.md](integration-plan.md) §7).
- CI on every PR (team-wide, [ADR 0213](decisions/0213-ci-on-every-pr.md)): `ci.yml` (tests, lint, types, audits, docs and spec checks) runs on every PR to `main`, about 3 minutes, like `security.yml`. Advisory, not a required check (that needs a paid plan or a public repo): do not merge a PR with a red job unless its body says why the failure is unrelated, and check this in review. Open: required checks, if the team pays or goes public.
