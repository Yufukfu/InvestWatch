# Demo script: analytics (M1, M2, M3)

The analytics part of the hand-in demo (Sun 2026-11-22, 10:30). It lists the documents to show, what each finding should look like, what to click, what to say, and a fallback if Gemini is down. Written by Damian's demo-prep session on 2026-11-22 between 02:55 and 03:50 local time. All numbers below were read from the running demo stack at that time.

## 0. Stack

- **Where:** a dedicated worktree, detached at `origin/main` `a0ad3d13` (`C:/Users/Damian/HackNation/InvestWatch-worktrees/demo`), so the demo does not depend on whatever branch the main checkout is on.
- **Env:** the root `.env`, copied in by a script that never prints values, plus `COMPOSE_PROJECT_NAME=iw-demo`. The LLM lines are those of ADR 0317 with the tested alternative model: `LLM_MODEL=gemma-4-26b-a4b-it`, `LLM_TIMEOUT_S=45`, `LLM_DOC_BUDGET_S=50`, `CLAIM_MIN_IDLE_MS=90000`.
- **Start:** one command, `docker compose up -d --build`. It passed on the first try, with no override file (all 10 services healthy, `/api/health` `ok`).
- **URLs:** dashboard `https://localhost:8443/`, API `https://localhost:8443/api/...`. The gateway uses a self-signed certificate: open the dashboard once before the demo and accept the certificate in the browser you will present from.
- **Do not rebuild or `down -v` before the demo.** The LLM verdicts live in the Redis cache of this stack (section 4). `docker compose restart` is fine, since Redis keeps its data.

## 1. Documents to show

Every source is in `scraper/seeds/*.toml` (seeded at start-up) except the M3 page, which was added through the dashboard API (`POST /api/sources`) for this demo. `scraper/seeds/sources.toml` says a named business is added there only by a human. If Damian wants ppcg.com.pl seeded permanently, he adds it to that file himself.

| # | Module | Source (seed) | URL | Role |
|---|---|---|---|---|
| 1 | M2 | XTB IKE (`sources.toml`, `firm_own`) | https://www.xtb.com/pl/ike | a registered firm's own ad page with rule failures |
| 2 | M1 | Comparic broker ranking (`sources.toml`, `third_party`) | https://comparic.pl/brokerzy-2/ | a third party advertising a registered firm |
| 3 | M1 (extra) | icobench Telegram signal groups list (`sources.toml`, `unknown`) | https://icobench.com/pl/akademia/najlepsze-grupy-telegram-dla-sygnalow-forex/ | sponsored-content label next to a registered firm |
| 4 | M3 | PPCG Stock home page (added via API, `unknown`, M3) | https://ppcg.com.pl/ | a paid service, outside the loaded register, that may recommend specific shares |
| 5 | negative | KNF public warnings (KNF seed) | https://www.knf.gov.pl/dla_konsumenta/ostrzezenia_publiczne | official source: no finding |
| 6 | negative | EY family office (`sources.toml`, `unknown`, M3) | https://www.ey.com/pl_pl/insights/law/ey-family-office | advisory vocabulary only: no M3 finding |

Telegram channels (`telegram.toml`) are scanned too and appear in the list. Their posts are about crypto only ("VIP za 149$", BTC longs and shorts). No share, bond, ETF or CFD is named, so S3.4 never fires and the gate keeps their M3 scores at 0.18-0.38, below the 0.4 threshold; a crypto-only recommendation is outside art. 2 anyway (S3.8). Use them to show the gate, not as a positive.

**Wording.** Say "the system flags this for an analyst", never "this firm breaks the law". A finding is a set of matched signals with quotes; the decision is the analyst's (status change, section 3).

## 2. Expected findings

Scores are as stored on the demo stack. `model.llm` is the model that decided at least one verdict, or `null` for rules-only. Section 4 says what is cached.

### 2.1 M2: XTB IKE (`https://www.xtb.com/pl/ike`)

- **Title:** "XTB S.A.: naruszenia – Oznaczenie reklamy, Informacja o ryzyku, Informacja podatkowa"
- **Score:** **0.368** (threshold 0.1), risk level high. `model.llm`: `gemma-4-26b-a4b-it` (rules-only it was 0.5).
- **Key rules:**
  - R1 firm identification: **pass**, quote "XTB S.A.".
  - R2 ad label: **fail** (no "reklama" / marketing label on the page).
  - R3 risk next to return claims: **fail**, quote "0% prowizji za kupno akcji i ETF-ów Do miesięcznego obrotu 100 000 EUR…".
  - R16 tax information: **fail** (tax advantage stated without the "depends on individual circumstances" caveat).
  - R15 forecasts, R17 implying KNF approval, R18 supervision as a safety argument: rules-only they were uncertain (R15, R18) or sent always (R17); the LLM decided all three as **pass** (`method: hybrid`). R17/R18 quote "jesteśmy regulowani przez renomowane instytucje nadzoru z całego świata." This is why the score dropped from 0.5 to 0.368: the model cleared two doubtful verdicts. It shows the LLM lowering a score, not only raising one.
  - The summary names them: "reguły R15, R17, R18 rozstrzygnięto z pomocą modelu językowego (gemma-4-26b-a4b-it)".
  - R4, R6, R12a, R12b, R14: `not_applicable` (no block render metadata on this page, no past-performance figures).
- **Say:** each of the 18 UKNF rules is a class plus a YAML entry; each failed rule has its legal basis and a verbatim quote, so the analyst can check it in seconds.

### 2.2 M1: Comparic broker ranking (`https://comparic.pl/brokerzy-2/`)

- **Title:** "comparic.pl reklamuje XTB S.A. (wezwanie do działania)"
- **Score:** **0.94** (threshold 0.65). `model.llm`: `gemma-4-26b-a4b-it` (rules-only 0.852).
- **Key signals:** S1.1 firm mentioned (**fail**, "XTB"); S1.2 affiliate link (**uncertain**, "utm_source=comparic"); S1.3 partnership label (pass: none, which does not rule out an ad); S1.4 call to action (**fail**, "Załóż konto"); S1.5 promotional tone (LLM; rules-only it is "Nie sprawdzono"); S1.6 author is not the firm (**fail**, "comparic.pl"); S1.7 aimed at Poland (**fail**, "100 PLN").
- **Firm card:** XTB S.A., brokerage house, in the register (`authorized: true`, match confidence 0.95). Advertiser comparic.pl, not in the register.
- **With the LLM** (as stored now): S1.5 is `method: llm`, **fail**, quoting "Ranking brokerów forex 2026 Polecamy brokera XTB Załóż konto i wpisz COMPARIC w polu “Kod referencyjny”…", and the score rises from 0.852 to 0.94. The quote is also the best argument that S1.2 (referral code) is right to be "do weryfikacji".

**Extra M1 (if time):** icobench.com, "icobench.com reklamuje Plus500EE AS (oznaczenie współpracy)", 0.818 rules-only (`model.llm` null: Gemini never answered in 10 attempts): S1.3 **fail** on "sponsorowane", which is the clearest "partnership label" example.

### 2.3 M3: PPCG Stock home page (`https://ppcg.com.pl/`)

- **Title:** "ppcg.com.pl: możliwe rekomendacje instrumentów finansowych"
- **Score:** **0.622** (threshold 0.4). `model.llm`: `null`, rules-only. Gemini returned 503 or timed out on all 10 warm-up attempts.
- **Key signals:** S3.1 not in the loaded register (**fail**); S3.5 paid model (**fail**, "abonamentowym"); S3.6 aimed at Poland (**fail**, "1,4 mld zł"); S3.4 recommendation of specific instruments: **uncertain**. The rule found a recommending verb near an instrument, but its quote is the page's tag list ("…akcje Allegro, akcje-gpw-analiza…"), not a clean sentence. S3.2 and S3.3 pass: the page uses no advisory vocabulary and offers no personalization.
- **Why it is above 0.4:** an uncertain S3.4 lifts the 0.4 cap, so the finding says "Do weryfikacji: S3.4". The LLM would confirm or reject it; if it ever answers `pass`, the score drops back under the cap. Say it honestly: this is a candidate for the analyst, and the weak quote is exactly why a human decides.
- **Same page, M1:** the home page also gets an M1 finding (0.818, `model.llm` `gemma-4-26b-a4b-it`, "ppcg.com.pl reklamuje ALIOR BANK S.A. – Biuro Maklerskie…"). The M1 call was the one that got answered during warm-up.
- **What the page is:** a subscription service with model portfolios and transaction signals on GPW shares (posts such as "Kupujemy nowe akcje do portfela głównego").
- **Say:** art. 76 advice needs a recommendation of a specific instrument **and** personalization. The summary says so itself: "Nie potwierdzono personalizacji (potrzeb i sytuacji klienta), której wymaga art. 76 – materiał może jedynie wskazywać na doradztwo inwestycyjne". Without S3.4 the score is capped at 0.4 (ADR 0308): education, or a paid group with no instrument named, is not advice.
- **Caveat:** this page is a blog home page and changes with every new post. A rescan during the demo creates a new content hash, so the cached LLM verdict no longer applies (section 4). Show the stored finding; do not rescan it live.

### 2.4 Negative controls

- **KNF warnings page:** the document is stored, analytics logs `document skipped … reason: official_source` (knf.gov.pl, uknf.gov.pl and gov.pl are never an advertiser, a firm or a publisher). No finding.
- **ey.com family office:** stored, `document skipped … reason: no_signals`. Advisory vocabulary alone does not make an M3 candidate. No finding.
- To show it: the findings list filtered to these URLs is empty; the analytics log line is `docker compose logs analytics | grep "document skipped"`.

### 2.5 Near-duplicates

**Skipped in this demo.** Near-duplicate grouping is MinHash in Redis (`iw:neardup:v1:*`, ADR 0314). It runs in the worker without embeddings, so `--profile llm` with `bge-m3` is not needed for it, and the demo laptop (16 cores, 31 GB RAM) is not the constraint. What is missing is a real reposted copy of a demo ad among the vetted sources:
- no two stored documents from different sources share their text (checked in the `documents` table);
- XTB IKZE, the closest candidate (same page template as IKE), was scanned and is a separate document (M2 0.553), not grouped with IKE.

If the jury asks: a repost is analyzed as usual, its summary names the original's URL, and it fires no second `finding.high_risk` for its group and module (`analytics/README.md`, "Modules and routing").

## 3. Click path in the dashboard (about 6 minutes)

The dashboard is one page (`https://localhost:8443/`): a header with the live-alert badge and the health badge, then the summary cards, the trend chart, the findings list and the calibration panel, top to bottom.

1. **Overview:** summary cards (total, by module, by risk level) and the trend chart. Health badge "System działa".
2. **Zgłoszenia** (findings list): filter Moduł = M2, sort by Wynik. Click the XTB IKE row. The address bar gets `?finding=<id>`, so each demo finding can be bookmarked ahead of time (ids in section 4).
3. **Finding detail** ("Szczegóły zgłoszenia"): "Dlaczego to zgłoszenie" (summary), the rules table with "Niespełniona" / "Niepewne", "Cytat z materiału" and "Podstawa prawna" per rule, the firm card, the screenshot when the renderer stored one, "Treść materiału" / "Pełna treść".
4. **Evidence pack export:** there is no button in the panel. Open `https://localhost:8443/api/findings/<id>/export?format=html` in a new tab (the id is in the address bar of the detail view): a printable Polish case file with the stored text, the raw HTML's SHA-256, the failed rules with legal basis and quotes. `format=json` gives the same as JSON.
5. **Status change:** in the detail panel, "Decyzja analityka": set Status to "W analizie" (`in_review`), add a "Notatka", "Zapisz". Then "Potwierdzone" or "Fałszywy alarm". Confirmed and false-positive labels feed the calibration curve.
6. Repeat 2-3 for M1 (comparic) and M3 (ppcg), pointing at the module-specific cards (advertiser, "Nadawca spoza rejestru KNF").
7. **Kalibracja progów** (calibration): choose a module, move the slider. Precision and recall ("Precyzja", "Czułość") and the number of alerts update; "Zapisz próg" writes `iw:settings:thresholds`, which analytics reads per document. Story in section 5.
8. **Live alert:** keep the dashboard open with the "Na żywo" badge. The dashboard has no scan button, so trigger the scan from a terminal: `POST https://localhost:8443/api/scans` with `{"source_id": "<id>"}` from `GET /api/sources`. Use a source not scanned yet, so it yields a new document (an unchanged page is deduplicated and analytics does not run again); the prepared one is section 4's "live alert" source. A `finding.high_risk` event appears as a toast within seconds of the analytics log line `finding built`.

## 4. LLM: what to say, what is cached

**What to say.** The challenge asks for free, open models. We run **Gemma 4** (open weights), hosted on Google's Gemini API through its OpenAI-compatible endpoint, under the mentor exception (ADR 0304, ADR 0317). Swapping to a fully local Gemma in Ollama is an `.env` change, no code change: README "LLM: hosted Gemma or local Ollama" (`analytics/README.md`), with `--profile llm`. The LLM only decides what the rules defer (S1.5, S1.4 confirmations, S3.3/S3.4, R3/R15/R17/R18), and each verdict must quote the document verbatim, or it becomes "do weryfikacji". If the endpoint fails, a circuit breaker opens and the findings are rules-only. The finding says so in its summary ("Tryb regułowy (bez modelu językowego)") and has `model.llm = null`.

**Cache.** Verdicts are cached in Redis, keyed by module, content hash and model (`iw:llm:v1:…`, ADR 0309). A second analysis of the same content with the same model makes no request to the API.

**What was warmed (2026-11-22, 02:00-02:41 UTC).** Each demo document was re-announced on `iw:documents` (an unchanged page rescanned through `POST /api/scans` is deduplicated and never reaches analytics), 65 s apart so that each try got the circuit breaker's trial call, with at most 10 tries per document. Gemini answered about one call in ten; the rest were 503 "high demand" or 45 s timeouts.

| Finding | Finding id | Score | `model.llm` | Tries |
|---|---|---|---|---|
| M1 comparic.pl | `9f92f7ba-160a-42ea-bf73-229b52f8ce2a` | 0.94 | `gemma-4-26b-a4b-it` | 2 |
| M2 xtb.com/pl/ike | `17f6e7e5-8b5d-4d09-a628-9ec62113cec5` | 0.368 | `gemma-4-26b-a4b-it` | 2 |
| M1 ppcg.com.pl (same page as M3) | `2ffb0878-183a-4c09-af78-cfb5cf4dc250` | 0.818 | `gemma-4-26b-a4b-it` | during the M3 tries |
| M3 ppcg.com.pl | `ff4de1af-eda9-4d11-9128-8ea4924937d4` | 0.622 | **null, rules-only** | 10, all failed |
| M1 icobench.com (extra) | `20d54053-c826-462e-984b-961783472ff9` | 0.818 | **null, rules-only** | 10, all failed (4 chunks, truncated) |

- Redis holds 9 verdict keys (6 `iw:llm:v1:M1:*`, 3 `iw:llm:v1:M2:*`), TTL 7 days, and Redis runs with AOF, so they survive `docker compose restart`.
- **Second pass check:** comparic and XTB IKE re-announced at 02:42 UTC: **0 requests** to `generativelanguage.googleapis.com` in the analytics log, 0.9 s and 1.2 s per document (against 20-40 s with a live call), same scores, `model.llm` kept.
- **Kept stable for the demo:** the scheduler's cron was cleared (`PATCH /api/sources/{id}` with `schedule_cron: null`) on comparic, XTB IKE and XTB forex, so no scheduled rescan before 10:30 can store a new, uncached version of a demo page. ppcg.com.pl was added without a cron. Restore the crons after the demo if wanted (`0 7 * * *`, `0 6 * * *`, `20 6 * * *`, as in `scraper/seeds/sources.toml`).
- **Live-alert source:** XTB forex (`0bdd4ea5-1678-457e-ab40-9660d2558584`, `https://www.xtb.com/pl/forex`) has never been scanned on this stack, so scanning it during the demo yields a new document and a new M2 finding. It is not cached: with Gemini down it is built rules-only within seconds; with Gemini slow it can take up to the 50 s document budget, so start the scan, explain, then point at the toast.
- The ids above are for this stack only. Open a finding with `https://localhost:8443/?finding=<id>`.

## 5. Thresholds (ADR 0316, ADR 0317)

- The defaults are measured, not chosen: the best-F1 point of the rules-only gold-set run, taking the higher end of the plateau (ties go to precision). **M1 0.65, M2 0.1, M3 0.4.**
- M3 is the exception: its best-F1 point is 0.25, but the default is raised to the S3.4 gate cap of 0.4 (ADR 0308). We prefer no false accusation of unauthorized advice over recall.
- Every `docker compose up` runs the evaluation once (`analytics-eval`) and stores the curve, so the calibration panel shows a measured curve from the first minute. The gold set is synthetic (69 documents from the challenge criteria), so the numbers say "the rules do what we specified", not real-world prevalence.
- **Slider, live numbers on this stack** (`GET /api/calibration?module=…`, rules-only gold run of `a0ad3d13`; they are newer than the slide deck, which predates the M2 P1 rules):

| Module | Threshold | Precision | Recall | Alerts on the gold set |
|---|---|---|---|---|
| M1 | 0.25 | 0.625 | 1.00 | 16 |
| M1 | **0.65 (default)** | 1.00 | 0.80 | 8 |
| M2 | **0.10 (default)** | 0.944 | 0.739 | 18 |
| M2 | 0.25 | 1.00 | 0.609 | 14 |
| M2 | 0.50 | 1.00 | 0.348 | 8 |
| M3 | 0.25 | 0.857 | 0.60 | 7 |
| M3 | **0.40 (default)** | 1.00 | 0.40 | 4 |

- Suggested move: M2 from 0.10 to 0.25 (precision reaches 1.0, four fewer alerts, recall drops), then back. "Zapisz próg" only if you want to keep it; the XTB IKE finding (0.368) stays above both.
- ADR 0317 adds the runtime limits that the hosted Gemma needs: `LLM_TIMEOUT_S=45`, `LLM_DOC_BUDGET_S=50`, and `CLAIM_MIN_IDLE_MS=90000` above the budget, so a slow model call is not mistaken for a dead worker.

## 6. Known limits (say them before the jury asks)

- **Visual rules need the renderer.** R4 (font size of the risk warning) and R6 (risk hidden in a footer) read the block render metadata from the page renderer. On a page or post without blocks they are `not_applicable`, as on XTB IKE here.
- **M3 recall is low by design.** Rules-only, S3.3 and S3.4 only mark candidates; the gate keeps scores at 0.4 or below without S3.4. Gold set at 0.4: precision 1.00, recall 0.40. Crypto-only signals (most Telegram channels) are outside art. 2 and are capped by S3.8.
- **12 of the 18 M2 rules are implemented** on `main` (R1, R2, R3, R4, R6, R11, R12 as R12a/R12b, R14, R15, R16, R17, R18: 13 catalogue entries). R5, R7-R10 and R13 are not built yet. The slide deck (`presentation-analytics.md`) still says 8: it was written from an older run.
- **The hosted model is slow and often unavailable** (measured on 2026-11-22: many 503 "high demand", 429 per-minute quota, 17-41 s per successful call on 26b). That is why the demo relies on the cache.

## 7. Fallback if Gemini is down (2 minutes)

1. **Do nothing different.** The demo findings are already stored, and the cached verdicts (section 4) are reused, so showing them needs no Gemini call.
2. If a live rescan is needed, scan a document whose verdicts are cached or one that is rules-only anyway (negative controls, Telegram posts). Avoid rescanning ppcg.com.pl (changing page).
3. If Gemini fails during a live scan: the analytics log shows `llm call failed … 503` then `llm verdicts dropped reason=llm_unavailable`, and the finding is built rules-only within a second or two. Show that as the safety net: the summary says "Tryb regułowy (bez modelu językowego)", `model.llm` is `null`, and the uncertain rules say "Nie sprawdzono … (wymaga modelu językowego)".
4. Last resort, all rules-only: comment out `LLM_BASE_URL` in `.env` and run `docker compose up -d analytics`. Findings are rules-only (`llm_mode: disabled` in the log); the stored findings stay.
