# Presentation: dashboard and architecture section, demo flow

Slide content for the hand-in PDF (issue #77), in the same format as [presentation-analytics.md](presentation-analytics.md): each `##` below is one slide, with speaker notes under **Notes**. The deck order, the title and the description are in [hand-in.md](hand-in.md). The click-by-click demo and the 3-minute video script are at the end of this file (not slides).

Every UI label below is copied from `web/src/` on `main` at `ba32bd27` (2026-11-22). Numbers about real data are Damian's recorded rehearsal in issue #78 (clean `docker compose up` from `main`, 17 seeded sources, one `POST /api/scans` each); they are not recomputed here. **The dashboard itself has not yet been rehearsed on that real data** (the dashboard part of #78 is still open): the flow below is what the code does, checked against the contract mock server and the tests, not a recorded run.

---

## 1. Architecture: six modules, one command

```
 scheduler / POST /api/scans ─▶ Redis iw:scan-requests ─▶ scraper worker(s)
     scraper ─▶ PostgreSQL documents + MinIO raw HTML ─▶ Redis Stream iw:documents
     analytics (M1, M2, M3, rules first, LLM second) ─▶ PostgreSQL findings + Redis iw:events
     api (FastAPI REST + Socket.IO) ─▶ HTTPS gateway (Caddy, :8443) ─▶ dashboard (React)
     LLM: any OpenAI-compatible endpoint (hosted DeepSeek Flash by default, ADR 0318, or local Gemma via Ollama, --profile llm)
```

- **Separate services, one `docker compose up`:** the root `compose.yaml` only `include:`s each module's own file (`infra/`, `web/`, `api/`, `analytics/`, `scraper/`), so each module also deploys on its own ([ADR 0202](decisions/0202-deployment-topology.md)).
- **Contracts between modules, not shared code:** `ScrapedDocument`, `Finding`, REST and events are JSON Schema and OpenAPI in `contracts/`, frozen as v1; the dashboard's API client is generated from `contracts/openapi.yaml` ([integration-plan.md](integration-plan.md) §3-§6).
- **Scales by adding workers:** scraper workers scale with `--scale worker=N` (limits and run lock in Redis); analytics reads `iw:documents` as a consumer group, so several workers can share it ([integration-plan.md](integration-plan.md) §2).
- **Open source, on-premise:** PostgreSQL, Redis, MinIO, Caddy, Ollama; the only exception is the hosted LLM (DeepSeek Flash by default, ADR 0318), which swaps to local Gemma by env only (mentor-approved, [ADR 0304](decisions/0304-llm-serving.md)).

**Notes:** The scraper knows nothing about analytics, and the dashboard knows only the REST contract and the event names; a module can be rewritten without touching the others. Only the gateway publishes a host port (`127.0.0.1:8443`); everything else sits on internal Docker networks. Hardening of each container (non-root, read-only root filesystem, `cap_drop: [ALL]`) is in `.docs/security-audit.md` "Service notes". A drawn diagram for this slide is tracked in #74; until then this text block is the slide.

---

## 2. Dashboard: from a finding to a decision

One page, top to bottom (`web/src/App.tsx`): header with live and health badges, summary cards, trend chart, findings list, calibration panel.

| Requirement (challenge §3.3) | What the dashboard does |
|---|---|
| Filter by date, source, risk level, module | `Moduł`, `Poziom ryzyka`, `Platforma`, `Minimalny wynik`, `Od dnia` / `Do dnia`, `Status`, free-text `Szukaj` (title, firm, account); sort by `Wynik` or `Wykryto`; paging |
| Trend charts (Recharts) | `Trend zgłoszeń` with a `Godzina` / `Dzień` switch, plus `Pokaż dane w tabeli` |
| Change a record's status | `Decyzja analityka` in the detail: `Nowe`, `W analizie`, `Potwierdzone`, `Fałszywy alarm`, `Zamknięte`, plus a note |
| Socket.IO alerts for high risk | `Wysokie ryzyko` toasts with `Pokaż`, and the `Na żywo` badge |
| Threshold panel, FP vs FN | `Kalibracja progów` (slide 4) |
| Open-source UI, props-based components | React 19, Redux Toolkit Query, Recharts, socket.io-client; components get data through props, data hooks live in a separate layer ([ADR 0204](decisions/0204-frontend-architecture.md)) |

- **The detail explains the verdict:** `Dlaczego to zgłoszenie`, every failed or uncertain rule with its verbatim quote (`Cytat z materiału`) and `Podstawa prawna`, the firm (`Firma w rejestrze KNF` or not, match confidence) and the advertiser (`Nadawca spoza rejestru KNF`, `Na liście ostrzeżeń KNF`), the content and, when the renderer ran, a screenshot.
- **Filters live in the URL:** a filtered view, or one finding (`?finding=<id>`), is a link an analyst can send.

**Notes:** All dashboard text is Polish; risk is shown as text plus colour, never colour alone. The source filter is the platform plus the free-text search; there is no per-source dropdown. Scraped text (titles, quotes, advertiser names) is rendered as plain text in its own `dir="auto"` element, never as HTML or Markdown, and tests pin `<img onerror>`, `javascript:` links and U+202E (issue #54).

---

## 3. Real-time alerts: one socket, no polling

- One Socket.IO connection through the gateway. `finding.created` and `finding.high_risk` refresh the list and the summary; `finding.updated` patches the status in place; on (re)connect the dashboard refetches, so nothing is lost while offline.
- A `finding.high_risk` event shows a toast: `Wysokie ryzyko`, module and score, the title, `Pokaż` (opens the detail) and `Zamknij`. At most 4 toasts, each for 20 s, paused while the pointer or keyboard focus is on it (`web/src/features/alerts/data/useRealtime.ts`).
- The header shows the connection state (`Na żywo`, `Łączenie…`, `Brak połączenia na żywo`) and the API health (`System działa`, `Częściowa awaria`, `System nie działa`, `Brak połączenia z API`).
- **On real data (#78):** analytics published 72 `finding.created` and 10 `finding.high_risk` events for 223 documents; 10 equals the number of findings at or above the thresholds (M1 0.65, M2 0.1, M3 0.4).

**Notes:** Who gets alerted is decided by the threshold in slide 4: analytics publishes `finding.high_risk` when a new finding's score reaches its module's threshold. Toasts never take focus on arrival and are announced politely to screen readers. The real-data counts are analytics' events from #78; the toasts on that data have not been watched in a recorded run yet.

---

## 4. Calibration: move the threshold, see the trade-off

- `Kalibracja progów`: pick a module (M1, M2, M3), then move the slider `Próg dla M2` over the points of `GET /calibration`.
- Next to the slider: `Wykryte naruszenia (TP)`, `Fałszywe alarmy (FP)`, `Przeoczone (FN)`, `Poprawnie pominięte (TN)`, `Precyzja`, `Czułość`, `F1`, each with its value at the current threshold, plus a precision/recall chart and a data table. Moving the slider is a preview only.
- `Zapisz próg` stores it (`PUT /settings/thresholds`); the API derives every finding's risk level on read from that threshold (`high` if `score >= t`, `medium` if `score >= t - 0.2`), so the findings, the summary and future alerts change at once (`Zapisano. Poziomy ryzyka zostały przeliczone.`). `Wróć do obecnego` undoes the preview.
- The curve comes from the gold-set evaluation that runs on every `docker compose up` (`analytics-eval`) plus the analysts' own labels (`Liczba oznaczonych próbek`).

| M2 threshold (gold set, rules-only run of `main` 61238394 with all 18 rules; [demo-analytics.md](demo-analytics.md) §5) | Precision | Recall | Alerts (TP+FP) |
|---|---|---|---|
| 0.05 (default) | 0.955 | 0.913 | 22 |
| 0.10 | 0.95 | 0.826 | 20 |
| 0.25 | 1.00 | 0.609 | 14 |
| 0.40 | 1.00 | 0.304 | 7 |

**Notes:** This is jury criterion "wpływ zmian parametrów progowych na wyniki w panelu kalibracji" made concrete: the numbers in the table are the panel's own data source (synthetic gold set, rules only; see the analytics section). The panel needs labelled data; with none it says `Za mało oznaczonych danych, aby skalibrować ten moduł.` Raising a threshold is a precision-for-recall trade the analyst sees before saving, and saving is explicit and global, with a warning that it changes every finding of that module.

---

## 5. Built to be judged: stability, libraries, console

- **No `console.log`:** a tested git hook rejects a commit that adds one to non-test JS/TS; `git grep` on `main` finds none in `web/` (the only hits are the CLI output of two `.claude/` tooling scripts and the hook's own message).
- **Dependencies scanned:** `npm audit` in `web/` reports 0 vulnerabilities (npm 10.9.2, `main` at `ba32bd27`, 2026-11-22); Python services use `pip-audit`, history with Gitleaks; results per PR ([ADR 0209](decisions/0209-supply-chain-scanning.md), [security-audit.md](security-audit.md)). Seven runtime dependencies in the dashboard: React, React DOM, react-is, Redux Toolkit, React Redux, Recharts, socket.io-client.
- **Data only from the backend:** no mock in the browser build; the mock lives only in the tests (MSW), so the demo shows the real API ([ADR 0206](decisions/0206-dashboard-data-from-backend.md)).
- **Errors stay local:** each chart section loads lazily and has its own error boundary (`Nie udało się pobrać danych trendu.`), so one failing request does not blank the page.
- **Hardened container:** the `web` service runs read-only with all capabilities dropped (`web/compose.yaml`).

**Notes:** The seven are the `dependencies` of `web/package.json`; react-is is there for Recharts. Since #100, `.github/workflows/security.yml` runs Gitleaks, OSV-Scanner, `pip-audit` and `npm audit` on every PR to `main` (advisory, not a required check). The `web` image build runs lint and the production build; the Vitest suite runs locally and in CI (issue #60), after #78 saw test timeouts under load in the image build.

---

## 6. Advertiser to firm: who promotes whom

The `Powiązania` page (`#powiazania`, module M1, change `advertiser-firm-view`, PR #129) answers "which third parties advertise which registered firms, and who keeps doing it".

- **Graph:** an inline-SVG graph of advertisers to KNF-registry firms; edge thickness is the number of findings for the pair, repeat advertisers are red and also carry a text label.
- **Repeat advertiser:** 2 or more distinct matched firms, or 5 or more findings.
- **Drill-down:** an edge, a firm or an advertiser opens a relation page with its findings; a row opens the finding detail with the quote and the signals.
- **Filters and a table view:** period, risk, minimum findings, repeat only; a `Graf | Tabela` toggle and a `Najczęstsi reklamodawcy` table that highlights an advertiser's edges.
- **Cheap by design:** built in the browser from `GET /findings?module=M1&page_size=200` (at most 3 pages, 600 findings, the cap is stated on screen); no new endpoint, contract change or dependency.

**Notes:** Source: `web/src/features/advertisers/`, `.docs/status/dashboard.md`. Limit to say aloud: on real data we did not check how many advertisers repeat, and on the static contract mock none does (4 advertisers, one finding each), so show it on the demo stack and read the KPI sentence, not a prepared claim. The graph is a view of M1 findings, not a separate analysis.

---

## 7. How we build with AI: spec, test, review, record, human merge

Every change takes the same path; the guards that matter are code, not prompts.

1. **Spec:** an OpenSpec proposal that a human approves.
2. **Test first:** a failing test, then the code, then a hand-written mutation check on every guard.
3. **Reviewer agent:** the read-only `iw-reviewer` on each task group's own pinned `BASE..HEAD`; every finding is verified against the code before it is fixed or rejected.
4. **Docs and log:** `iw-docs-update` with `docs-check`, an AI-log entry, the change archived as the last commit.
5. **Human merge:** the agent may push its own branch and open the PR (ADR 0207); the human approves and merges every PR.

On `main` at `313c625b`: **89** archived OpenSpec changes, **42** specs, **42** ADRs, **134** AI-log entries, **118** merged PRs, **1276** commits, 7 project skills (`iw-*`) and one reviewer agent.

**Denied by the tested git hook** (`.claude/hooks/git-guard.js`): force push, any push to `main`, `--all`/`--mirror`, `reset --hard`, whole-tree checkout, amending a pushed commit; on commit a staged `.env`, `console.log` in JS/TS, service code with no active OpenSpec change, and contract edits after the freeze; and, from ADR 0207, any remote but `origin`, rewiring a remote, deleting or updating a branch other than the current one, and merging or approving through `gh api`.

**Notes:** Sources: `.claude/SDLC.md`, `.claude/CODE_REVIEW.md`, ADR 0207, `.docs/ai-workflow.md` (the log, including rules that misled us). Counts: `ls openspec/changes/archive | wc -l`, `ls openspec/specs | wc -l`, `ls .docs/decisions | grep -c '^0[1-3]'`, `ls .docs/ai-log | grep -c '^20'`, `gh pr list --state merged --limit 500 --json number -q length`, `git rev-list --count HEAD`. Honest limits: the hook reads command text only, so it catches mistakes, not a determined agent, and every `IW_*` escape used is reported in the PR body; CI is advisory, not a required check. Scraper-specific evidence (what review caught that green tests had not) is on scraper slide 5.

---

## 8. What is unique

- **Rules first, LLM second:** deterministic rules decide what they can; the model only settles the doubtful cases and must quote the document, and the quote is verified against the text.
- **A legal basis on every finding:** M2 rules carry the article of Delegated Regulation 2017/565 (M3: art. 76), shown next to the evidence.
- **Calibration that acts:** saving a threshold in the dashboard recomputes every finding's risk level at once, with precision, recall and TP/FP/FN/TN shown beside it.
- **A swappable model:** the hosted LLM (DeepSeek Flash by default, ADR 0318) becomes a local open model (Gemma via Ollama) by environment variables only; without any model the system runs on rules.
- **Advertiser to firm graph:** repeat third-party promoters of registered firms in one view (slide 6).

**Notes:** Each bullet maps to code or an ADR: `llm-analysis` spec and ADR 0304/0318 (quote check, env-only swap), `m2_rules.yaml` (`legal_basis`), `web-calibration` spec (`PUT /settings/thresholds`). Do not call the numbers real-world accuracy: the gold set is synthetic.

---

# Demo flow (live demo and 3-minute video)

Not slides. The live order follows the jury's criteria in challenge §6: scraping works, classification and the threshold, UI and real-time alerts.

## Before the demo (once, about 30 min ahead)

1. **On the pre-warmed demo stack (`iw-demo`), do not run `down -v` or rebuild:** the LLM verdicts live in that stack's Redis cache and the demo stack's cache holds verdicts from the old hosted default, Gemma on the Gemini API, which mostly returned 503s (the default is DeepSeek Flash since ADR 0318, but the cache was filled before), so a fresh stack without an LLM key would show rules-only findings ([demo-analytics.md](demo-analytics.md) §0 and §4). `docker compose restart` is safe. Only on a new machine: `./scripts/init-env.sh` if there is no `.env`, then `docker compose up --build -d`.
2. LLM: the demo findings come from the cache (demo-analytics.md §4 lists their ids). If the cache is gone, either run local Gemma (`docker compose --profile llm up -d`, runbook in the analytics section, slide 7) or accept rules-only findings and say so.
3. Live-alert source: XTB forex (`https://www.xtb.com/pl/forex`, id in demo-analytics.md §4) has never been scanned on the demo stack, so scanning it live yields a new M2 finding. It is not cached: rules-only it is built in seconds, but with a slow Gemini it can take up to the 50 s document budget (ADR 0317). Its cron, and those of comparic and XTB IKE, are cleared on that stack, so no scheduled rescan stores an uncached version before 10:30.
4. Open https://localhost:8443 in a browser that trusts the local certificate (`infra/README.md`), check `System działa` and `Na żywo` in the header.
5. Do not open the Grant Thornton family-office finding: it is a negative control that scores high-risk M3 (0.78) only because the LLM was down (#78, gap 2). If the LLM is up for the demo, check its score again.
6. Record the backup video now (script below), in case the live run fails.

## Live, click by click (about 5 min)

| # | Action | What the jury sees | Say |
|---|---|---|---|
| 1 | Page loaded, point at the header | `InvestWatch`, `Na żywo`, `System działa`; cards `Wszystkie zgłoszenia`, `Wysokie ryzyko`, `Nowe` | "One `docker compose up`: scraper, analytics, API and this dashboard, on real pages scraped this morning." |
| 2 | `Trend zgłoszeń`: click `Godzina`, then `Dzień` | the scan run as a spike | "Findings over time; table view for accessibility." |
| 3 | Scan XTB forex in a terminal (`POST /api/scans` with its `source_id`) | after the scrape and analysis, a `Wysokie ryzyko` toast with module and score; the cards and list refresh | "Socket.IO push, no reload." Start the scan, then explain: the toast can take up to about 50 s if Gemini is slow; go on and come back to it. |
| 4 | Click `Pokaż` on the toast | the detail: `Dlaczego to zgłoszenie`, failed rules with `Cytat z materiału` and `Podstawa prawna`, `Podmioty` | "Each verdict quotes the page and names the legal basis; the analyst does not have to trust a score." |
| 5 | In `Decyzja analityka` set `W analizie`, type a note, click `Zapisz` | `Zapisano.`; the status changes in the list behind | "Status workflow; the change is broadcast to other open dashboards (`finding.updated`)." |
| 6 | Close the detail; in the filters pick `Moduł` = `M1 · Finfluencerzy`, `Poziom ryzyka` = `Wysoki` | only high-risk M1 findings (in #78: the Take Profit guide, the Comparic ranking, the icobench list) | "Filters stay in the URL, so this view is a link." |
| 7 | Click `Wyczyść filtry`, then `Moduł` = `M3 · Usługi bez zezwolenia` | M3 findings, e.g. the Moneteo review (high, 0.50 in #78) | "Shadow advisory: firms outside the KNF register offering advice." |
| 8 | Scroll to `Kalibracja progów`, pick `M2`, move the slider from the default 0.05 to 0.25 | TP/FP/FN/TN, precision 0.955 → 1.00, recall 0.913 → 0.609, alerts 22 → 14 on a build of current `main` (a stack built before ADR 0319 starts at 0.10; read the panel, not this cell), the chart marker moves | "Threshold up: fewer false alarms, more misses. Preview only, nothing changed yet." |
| 9 | Optional: click `Zapisz próg` | `Zapisano. Poziomy ryzyka zostały przeliczone.`; M2 findings scoring between the old and the new threshold drop from high, so the `Wysokie ryzyko` card may go down | The XTB IKE finding (0.368) stays high at 0.25. Do not save 0.40: XTB IKE would drop. How far the card moves depends on the stack's other M2 scores; read it at the rehearsal. |
| 10 | `Wróć do obecnego` is only for the preview; if you saved, move back to 0.05 and `Zapisz próg` again | the card goes back | "The threshold is the analyst's choice, measured, not hard-coded." |

## 3-minute video script

Record at 1280 px wide, browser zoom 100 %, the stack prepared as above. Timings are targets.

| Time | Screen | Voice-over (Polish on the video if the jury is Polish; this is the content) |
|---|---|---|
| 0:00-0:15 | title slide | InvestWatch: monitoring of investment ads and offers online for UKNF; scraper, three analytics modules, dashboard, one `docker compose up`. |
| 0:15-0:35 | terminal: `docker compose ps` | Separate services: scraper worker, scheduler, analytics, API, web, Postgres, Redis, MinIO, gateway; open-source, on-premise, LLM swappable to local Gemma. |
| 0:35-1:05 | dashboard header, cards, trend; then the scan request and the toast | Real data: in our rehearsal 17 sources, 223 documents, 72 findings, 10 high-risk (#78). A new high-risk finding arrives live. |
| 1:05-1:45 | `Pokaż`, the detail, status change | Why it was flagged: rule, quote, legal basis, firm in the KNF register or not; the analyst records a decision. |
| 1:45-2:05 | filters M1 high, then M3 | M1 finfluencers and third parties, M3 shadow advisory; filters by module, risk, platform, date, status. |
| 2:05-2:40 | calibration M2: slider, `Zapisz próg` | Thresholds are measured on a gold set; moving one trades false alarms for misses, and saving recomputes risk levels everywhere. |
| 2:40-3:00 | the repo: `openspec/`, `.docs/ai-log/`, `.claude/` | Built spec-first with AI agents: OpenSpec, tests first, a reviewer agent, git guards, an AI log for every change. |
