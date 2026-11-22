# Hand-in package

What the HackNation form needs (challenge "Opis Wyzwania", §4 "Wymagania formalne"): a detailed description and the title, a PDF presentation, the code description / README and the repository; optionally a video of at most 3 minutes. The challenge materials are in Polish, so the title and the description below are in Polish first, with an English version to reuse if the form or the jury needs one. Issue #77.

Every number below comes from a named source: the gold-set runs in [presentation-analytics.md](presentation-analytics.md) (synthetic set, rules only and with DeepSeek Flash), Damian's recorded rehearsal on real data in issue #78, or a count on `main` at `313c625b` (2026-11-22). Refresh the counts just before submitting (commands at the end).

## Title

**PL:** InvestWatch: automatyczny monitoring reklam i ofert inwestycyjnych w sieci dla UKNF

**EN:** InvestWatch: automated monitoring of online investment ads and offers for UKNF

## Description (PL)

InvestWatch to działający prototyp systemu, który zbiera z internetu i mediów społecznościowych materiały promujące instrumenty i usługi inwestycyjne na polskim rynku, ocenia je trzema modułami analitycznymi i pokazuje wyniki analitykowi UKNF w panelu z alertami w czasie rzeczywistym. Cały stos uruchamia się jedną komendą `docker compose up`.

**Co robi**
- **Silnik scrapujący:** kolejka zadań (arq na Redis), harmonogram cron, ręczne skanowanie z API, klient TLS podszywający się pod przeglądarkę, rotacja tożsamości przeglądarki (User-Agent razem z nagłówkami i profilem TLS) i proxy, poszanowanie `robots.txt` i limitów na domenę, ochrona przed SSRF, opcjonalny renderer Playwright dla zrzutów ekranu i układu strony. Strony WWW, publiczne kanały Telegram oraz X i YouTube (na żądanie); dane w PostgreSQL, surowy HTML w MinIO.
- **Moduł 1 (finfluencerzy i podmioty trzecie):** wykrywa reklamy firm z rejestru KNF (749 firm z czterech list KNF) publikowane przez osoby trzecie: siedem ważonych sygnałów (wzmianka o firmie, link afiliacyjny lub kod, oznaczenie współpracy, wezwanie do działania, ton promocyjny, autor spoza firmy, kierowanie do Polaków). Wynik: firma, reklamodawca, treść, URL.
- **Moduł 2 (informacja o ryzyku):** materiały samych firm sprawdzane regułami z załącznika UKNF (art. 44 rozporządzenia delegowanego 2017/565); 14 z 18 reguł zaimplementowanych (15 z 19 wpisów katalogu, bo R12 to dwie reguły), każda z cytatem z materiału i podstawą prawną; reguły wizualne czytają rozmiar czcionki i położenie bloków, gdy scraper renderuje stronę (renderer domyślnie wyłączony).
- **Moduł 3 (shadow advisory):** podmioty spoza rejestru KNF oferujące w praktyce doradztwo inwestycyjne (art. 76): słownictwo doradcze, personalizacja, rekomendacja konkretnych instrumentów, płatne sygnały; twarda bramka, by sama edukacja nie była oskarżeniem.
- **Reguły najpierw, LLM potem:** wszystko, co da się sprawdzić deterministycznie, liczą reguły; model językowy rozstrzyga tylko przypadki wątpliwe i musi zacytować dokument. Model jest wymienny przez zmienne środowiskowe: hostowany DeepSeek Flash lub lokalny, otwarty model Gemma w Ollamie (`--profile llm`); odpowiedzi są cache'owane, a bez modelu system działa na samych regułach.
- **Powiązania reklamodawca-firma (M1):** widok `#powiazania` pokazuje graf reklamodawców i firm z rejestru KNF, z oznaczeniem reklamodawców powtarzających się i przejściem do zgłoszeń danej pary.
- **Panel (React):** filtry po module, poziomie ryzyka, platformie, wyniku, dacie i statusie; wykres trendu (Recharts); szczegóły zgłoszenia z cytatami i podstawą prawną; zmiana statusu z notatką; alerty wysokiego ryzyka przez Socket.IO; panel kalibracji progów z precyzją, czułością, TP/FP/FN/TN i zapisem progu, który od razu przelicza poziomy ryzyka.

**Co wyróżnia**
- Reguły najpierw, LLM potem, z zweryfikowanym cytatem z dokumentu przy każdym rozstrzygnięciu modelu.
- Podstawa prawna przy każdym zgłoszeniu (art. 44 rozporządzenia delegowanego 2017/565, art. 76 dla M3).
- Kalibracja, która działa: zapis progu przelicza poziomy ryzyka wszystkich zgłoszeń.
- Hostowany LLM wymienny na lokalny model samą konfiguracją środowiska.
- Graf reklamodawca-firma: kto powtarzalnie promuje firmy z rejestru.

**Wyniki**
- Na prawdziwych danych (próba generalna, #78): 17 źródeł (13 stron WWW, 4 kanały Telegram), 223 dokumenty, 0 błędów analityki, 72 zgłoszenia (M1 54, M2 5, M3 13), 10 alertów wysokiego ryzyka.
- Na zbiorze wzorcowym (69 dokumentów syntetycznych napisanych z kryteriów UKNF, domyślne progi M1 0,75, M2 0,1, M3 0,4), precyzja / czułość z hostowanym LLM (DeepSeek Flash): M1 1,00 / 1,00; M2 0,95 / 0,826; M3 1,00 / 0,40. Same reguły, bez LLM: M1 1,00 / 0,70; M2 0,947 / 0,783; M3 1,00 / 0,40. Progi M1 i M2 są zmierzone na tym zbiorze; próg M3 (0,4) wynika z bramki S3.4. Zbiór jest syntetyczny, bo nie otrzymaliśmy próbek od UKNF; prawdziwe próbki dodaje się bez zmiany kodu.

**Architektura**
Lekkie, osobne serwisy (scraper, analytics, api, web, infra), każdy z własnym `compose.yaml`, połączone kontraktami JSON Schema i OpenAPI (zamrożone jako v1) oraz strumieniami Redis. Skalowanie przez kolejne workery scrapera i analityki. Nowe źródło to kilka linii TOML, nowa platforma to jeden moduł parsera, nowa reguła M2 to wpis YAML i jedna klasa. Stos open source i on-premise (PostgreSQL, Redis, MinIO, Caddy, Ollama); jedyny wyjątek, hostowany LLM, zatwierdził mentor i zamienia się na lokalny model samą konfiguracją.

**Proces z asystentami AI**
Każda zmiana przechodzi tę samą ścieżkę z Claude Code: specyfikacja OpenSpec zatwierdzona przez człowieka, najpierw test, który nie przechodzi, ręczny test mutacyjny, przegląd przez osobnego agenta-recenzenta, aktualizacja dokumentacji i wpis w dzienniku AI, a na końcu PR, który scala zawsze człowiek. Hook gita blokuje m.in. force push, push do `main`, `console.log` w kodzie, plik `.env` w commicie i zmiany zamrożonych kontraktów. Stan na `main`: 89 zarchiwizowanych zmian OpenSpec, 42 decyzje architektoniczne (ADR), 134 wpisy dziennika AI, 118 scalonych PR-ów. Hook blokuje też push na inny remote niż `origin`, zmianę remote'a, usuwanie lub aktualizację innej gałęzi niż bieżąca oraz scalanie i zatwierdzanie przez `gh api`.

**Bezpieczeństwo**
Skanowanie zależności (`npm audit`, `pip-audit`) i historii repozytorium (Gitleaks), sekrety wyłącznie w nieśledzonym `.env`, kontenery bez roota z systemem plików tylko do odczytu, tekst ze scrapowanych stron wyświetlany zawsze jako zwykły tekst.

**Ograniczenia (uczciwie)**
Telegram, X i YouTube mają działające kolektory. Facebook, Instagram i TikTok są w enumie platform kontraktu danych, ale nie mają kolektora: ich publiczne endpointy oEmbed zwracają tylko iframe, bez treści i autora, więc prawdziwa treść wymagałaby tokenu aplikacji lub zalogowanego API (Meta Graph, TikTok Research API) albo scrapowania HTML wbrew regulaminom. Zrezygnowaliśmy z nich świadomie, zamiast dostarczać pusty kolektor; nowa platforma to jeden adapter i rejestracja w rejestrze social. W M2 działa 14 z 18 reguł (brakuje R5, R7, R8, R13). Liczby jakości pochodzą ze zbioru syntetycznego; z LLM zmierzyliśmy tylko hostowany DeepSeek Flash, lokalnej Gemmy nie mierzyliśmy na zbiorze wzorcowym. W próbie generalnej hostowany LLM był niedostępny, więc 71 z 72 zgłoszeń policzyły same reguły.

## Description (EN)

InvestWatch is a working prototype that collects investment promotion from the web and social media, scores it with three analytics modules and shows the results to a UKNF analyst in a dashboard with real-time alerts. The whole stack starts with one `docker compose up`.

- **Scraper:** job queue (arq on Redis), cron scheduler and manual scans from the API, a browser-impersonating TLS client, rotating browser identities (User-Agent with matching headers and TLS profile) and proxies, `robots.txt` and per-domain limits, SSRF guards, an optional Playwright renderer for screenshots and layout. Web pages, public Telegram channels, and X and YouTube on demand; PostgreSQL for data, MinIO for raw HTML.
- **M1, finfluencers and third parties:** ads for firms in the KNF register (749 firms from four KNF lists) published by someone else; seven weighted signals; output: firm, advertiser, content, URL.
- **M2, risk information:** the firms' own marketing checked against the UKNF rules (art. 44 of Delegated Regulation 2017/565); 14 of 18 rules implemented (15 of 19 catalogue entries, since R12 is two), each with a verbatim quote and its legal basis.
- **M3, shadow advisory:** entities outside the register that in fact offer investment advice (art. 76), with a hard gate so that education alone is never flagged as advice.
- **Rules first, LLM second:** the model only decides the cases the rules defer and must quote the document; hosted DeepSeek Flash or the local open model Gemma (Ollama) by env only; answers are cached; rules-only if it is down.
- **Advertiser to firm graph (M1):** the `#powiazania` view shows advertisers and registry firms as a graph, marks repeat advertisers and opens the findings of a pair.
- **Dashboard (React):** filters, trend chart, finding detail with quotes and legal basis, status workflow, Socket.IO high-risk alerts, and a calibration panel where moving and saving a threshold recomputes risk levels at once.
- **What is unique:** rules first and LLM second with a verified quote from the document; a legal basis on every finding; calibration that acts (saving a threshold recomputes risk levels); a hosted LLM swappable to a local model by environment only; the advertiser to firm graph.
- **Results:** real-data rehearsal (#78): 17 sources, 223 documents, 72 findings, 10 high-risk alerts, 0 analytics errors. Synthetic gold set (69 documents, thresholds M1 0.75, M2 0.1, M3 0.4), precision / recall with DeepSeek Flash: M1 1.00 / 1.00, M2 0.95 / 0.826, M3 1.00 / 0.40; rules only: M1 1.00 / 0.70, M2 0.947 / 0.783, M3 1.00 / 0.40.
- **Process:** spec-driven development with Claude Code (OpenSpec, test first, reviewer agent, git guards, AI log); on `main`: 89 archived changes, 42 ADRs, 134 AI-log entries, 118 merged PRs; the human merges every PR, and the git hook also denies pushes to any remote but `origin`, remote rewiring, touching any branch but the current one, and merging or approving through `gh api`.
- **Limits:** Telegram, X and YouTube are live collectors. Facebook, Instagram and TikTok are in the data contract's platform enum but have no collector: their public oEmbed endpoints return only an embed iframe, with no caption or author, so real content would need app-token or logged-in API access (Meta Graph, TikTok Research API) or HTML scraping against their terms. We left them out deliberately rather than ship a hollow collector. A new platform = one adapter plus registration in the social registry. 14 of 18 M2 rules (R5, R7, R8 and R13 not built); quality numbers are synthetic, measured rules-only and with hosted DeepSeek Flash; local Gemma is not measured on the gold set.

## PDF: slide order

One deck, assembled from four files. 23 slides; cut the optional ones if the slot is short.

| # | Slide | Source | Jury criterion (§8) |
|---|---|---|---|
| 1 | Title: name, one line, team, repository URL | this file, "Title" | |
| 2 | The problem and the three questions | analytics slide 1 | 4 (fit to the brief) |
| 3 | Architecture: six modules, one command | dashboard slide 1 | 3 (architecture) |
| 4 | Scraper: queue, fetch ladder, one writer | scraper slide 1 | 1, 3 |
| 5 | Polite, hard to abuse, honest about provenance | scraper slide 2 | 1 |
| 6 | Coverage on real data: 17 sources, 223 documents | scraper slide 3 | 1 (§6: scraping works) |
| 7 | M1: third-party ads | analytics slide 2 | 1, 4 |
| 8 | M2: 18 UKNF rules | analytics slide 3 | 1, 4 |
| 9 | M3: shadow advisory | analytics slide 4 | 1, 4 |
| 10 | Calibration: thresholds are measured | analytics slide 5 | 1 (§6: threshold effect) |
| 11 | Dashboard: from a finding to a decision | dashboard slide 2 | 1, 4 |
| 12 | Advertiser to firm graph (`#powiazania`, M1) | dashboard slide 6 | 1, 4 |
| 13 | Real-time alerts | dashboard slide 3 | 1 (§6: UI and alerts) |
| 14 | Calibration panel | dashboard slide 4 | 1 (§6: threshold effect) |
| 15 | Demo (live, or a still of the dashboard with the video link) | dashboard "Demo flow" | 1 |
| 16 | Open for extension: a new rule in two files | analytics slide 6 | 3 |
| 17 | Open for extension: a source in one table, a platform in one module | scraper slide 4 | 3 |
| 18 | Open model: hosted DeepSeek Flash or local Gemma | analytics slide 7 | 4 (open source, on-premise) |
| 19 | Built to be judged: stability, libraries, console | dashboard slide 5 | 4 (§6: libraries, console.log) |
| 20 | How we build with AI: spec, test, review, record, human merge | dashboard slide 7 (scraper slide 5 is the scraper-only backup) | 2 (AI process) |
| 21 | What is unique | dashboard slide 8 | 1, 4 |
| 22 | Honest limits and next steps | this file, "Ograniczenia" plus the open issues (#70, #71, #72, #73) | 5 |
| 23 | Thank you / repository link / how to run (`docker compose up`) | root README Quick Start | |

Sources:
- Analytics slides: [presentation-analytics.md](presentation-analytics.md), on `main`.
- Dashboard slides and demo flow: [presentation-dashboard.md](presentation-dashboard.md).
- Scraper slides: [presentation-scraper.md](presentation-scraper.md), merged (PR #98), counts refreshed at `313c625b`.
- Architecture and scale-out slides: [presentation-architecture.md](presentation-architecture.md) (back-up slides after slide 3).

## Still for humans

- [ ] **Decide the title** (above) and paste the description into the hand-in form; check the form's language and length limit, and cut the PL text if needed.
- [ ] **Build the PDF** from the slide order above (Google Slides or similar), export to PDF, check it opens and the code blocks are legible.
- [ ] **Rehearse the dashboard on real data** (dashboard part of #78), then fix the demo flow where it differs, in particular step 9 (the predicted card change).
- [ ] **Record the video** (at most 3 min, script in [presentation-dashboard.md](presentation-dashboard.md)) and upload it where the form asks.
- [ ] **Real UKNF samples** on analytics slide 5, if they arrived (#73).
- [ ] **README:** check the root README Quick Start once more on a clean clone (the api is in compose; hardware requirements are there; service configuration moved to [infra/README.md](../infra/README.md)).
- [ ] **`doc/`:** the UKNF materials are committed and the README now says so; whether to remove them before hand-in is the human's call. Removing it breaks the `../doc/` links in `.docs/INDEX.md`, the root README and this file's sources, so update those in the same PR and rerun `docs-check`; `.docs/integration-plan.md` also still says they are removed.
- [ ] **Repository:** make sure the jury can open it (visibility, link in the form) and `main` is green.
- [ ] **Submit** before Sun 2026-11-22 10:30 Europe/Warsaw.

Refresh the counts on `main` before submitting:

```bash
ls openspec/changes/archive | wc -l                      # archived OpenSpec changes
ls .docs/decisions | grep -c '^0[1-3]'                   # ADRs
ls .docs/ai-log | grep -c '^20'                          # AI-log entries
git rev-list --count HEAD                                # commits
gh pr list --state merged --limit 500 --json number -q length   # merged PRs
```
