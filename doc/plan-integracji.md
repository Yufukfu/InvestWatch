# InvestWatch – plan integracji modułów

Wersja kontraktów: **v1** (zamrażamy do 14:30 w sobotę; zmiany tylko po uzgodnieniu w zespole i z podbiciem wersji).

## Zespół i odpowiedzialności

| Osoba | Moduł | Właściciel czego |
|---|---|---|
| **A** | Scraper | kolektory (WWW + social media), kolejka zadań, harmonogram, zapis `documents` + obiekty w MinIO |
| **B** | Dashboard | frontend (React), filtry, wykresy, alerty WebSocket, panel kalibracji |
| **C** (my) | Analityka + integracja | schemat bazy, kontrakty, REST API + WebSocket gateway, moduły M1–M3, rejestr firm, docker-compose |

Decyzja do potwierdzenia: **REST API buduje C** (cienka warstwa nad tą samą bazą). B pracuje od pierwszej minuty na danych mockowych zgodnych z kontraktem z sekcji 5, a A nie jest obciążony niczym poza zbieraniem danych.

## 1. Architektura

```
                ┌──────────────┐  XADD iw:documents   ┌──────────────────┐
 harmonogram ──▶│  scraper (A) │ ───────────────────▶ │  analytics (C)   │
 (cron/beat)    │ Playwright,  │                      │ preprocessing,   │
                │ httpx, UA/   │──┐                ┌──│ M1/M2/M3, LLM    │
                │ proxy rotacja│  │                │  └────────┬─────────┘
                └──────────────┘  │ INSERT         │ INSERT    │ PUBLISH iw:events
                                  ▼                ▼           ▼
                      ┌────────────────────┐   ┌──────────┐  ┌────────────────┐
                      │ PostgreSQL         │   │ MinIO    │  │ api (C)        │
                      │ sources, documents,│   │ html,    │  │ FastAPI REST + │
                      │ findings, registry │   │ screeny  │  │ Socket.IO      │
                      └─────────▲──────────┘   └──────────┘  └───────┬────────┘
                                └──────────────── SELECT ────────────┤
                                                                      ▼
                                                            ┌────────────────┐
                                                            │ dashboard (B)  │
                                                            └────────────────┘
                         ollama (lokalny LLM + embeddingi) ◀── analytics
```

Serwisy w `docker-compose.yml` (jedna komenda `docker compose up`):
`postgres`, `redis`, `minio`, `ollama`, `scraper`, `scheduler`, `analytics`, `api`, `dashboard`.

Struktura repo (osobne serwisy, każdy z własnym Dockerfile i zależnościami):

```
/scraper     – A
/analytics   – C
/api         – C
/dashboard   – B
/contracts   – JSON Schema + przykładowe dane (mocki) – C
/doc         – materiały UKNF, plany, dziennik pracy z AI
docker-compose.yml, .env.example
```

## 2. Punkty styku

| # | Od → do | Mechanizm | Treść |
|---|---|---|---|
| 1 | scraper → baza | `INSERT` do `documents` | dokument wg schematu `ScrapedDocument` (sekcja 3) |
| 2 | scraper → MinIO | bucket `iw-raw` | `html/{document_id}.html`, `shot/{document_id}/{viewport}.png`, `media/{document_id}/{n}.{ext}` |
| 3 | scraper → analityka | Redis Stream `iw:documents` | `{"document_id": "<uuid>", "schema": "v1"}` – **po** commicie w bazie |
| 4 | analityka → baza | `INSERT` do `findings` | wynik wg schematu `Finding` (sekcja 4) |
| 5 | analityka → API | Redis Pub/Sub `iw:events` | zdarzenia (sekcja 6) |
| 6 | API → dashboard | REST + Socket.IO | sekcje 5 i 6 |
| 7 | analityka → ollama | HTTP `OLLAMA_URL` | generowanie i embeddingi |

Redis Stream z consumer group `analytics` daje nam: niezależność od języka scrapera, ponawianie (`XPENDING`/`XCLAIM`) i możliwość wielu workerów analityki. Scraper nie musi nic wiedzieć o analityce.

## 3. Kontrakt: `ScrapedDocument` (scraper → analityka)

Tabela `documents`; kolumny proste + `payload JSONB` na resztę.

```jsonc
{
  "id": "uuid",
  "source_id": "uuid",                  // wpis w tabeli sources
  "platform": "web|facebook|instagram|tiktok|youtube|x|forum|other",
  "source_kind": "firm_own|third_party|unknown", // czy materiał publikuje sama firma (M2) czy ktoś inny (M1/M3)
  "url": "https://...",
  "canonical_url": "https://...",
  "fetched_at": "2026-11-21T14:05:00Z",
  "published_at": "2026-11-20T09:00:00Z | null",
  "http_status": 200,
  "lang": "pl | null",                  // opcjonalne – analityka i tak wykrywa
  "title": "string | null",
  "text": "czysty tekst całości materiału",
  "content_hash": "sha256 znormalizowanego tekstu", // deduplikacja
  "author": {                           // dla social media / blogów
    "name": "string | null",
    "handle": "@nick | null",
    "profile_url": "https://... | null",
    "followers": 12345
  },
  "links": [ { "href": "https://...", "text": "string", "rel": "nofollow sponsored | null" } ],
  "media": [ { "type": "image|video", "object_key": "media/...", "alt": "string | null" } ],
  "html_object_key": "html/{id}.html | null",
  "screenshots": { "desktop": "shot/{id}/desktop.png", "tablet": "...", "mobile": "..." },

  // Tylko dla stron WWW renderowanych Playwrightem – potrzebne do reguł wizualnych M2 (R4–R8, R13)
  "blocks": [
    {
      "viewport": "desktop|tablet|mobile",
      "text": "Inwestuj z zyskiem do 20% rocznie",
      "tag": "h1|p|span|small|footer|...",
      "font_size_px": 32,
      "font_weight": 700,
      "color": "#111111",
      "background_color": "#ffffff",
      "bbox": [x, y, w, h],
      "visible": true,                  // display/visibility/opacity/rozmiar > 0
      "in_viewport_on_load": true,      // widoczne bez przewijania
      "requires_interaction": false,    // ukryte w <details>, akordeonie, tooltipie, modalu
      "region": "main|header|footer|legal|aside|overlay",
      "overflow_clipped": false         // tekst ucięty (responsywność)
    }
  ],
  "scrape_meta": { "scraper": "playwright|httpx|api", "user_agent": "...", "proxy": "id | null", "duration_ms": 1830 }
}
```

Minimum, żeby analityka zadziałała: `id, platform, url, fetched_at, text, source_kind`.
`blocks` i `screenshots` – wymagane tylko do reguł wizualnych; bez nich reguły R4–R8, R13 dostają status `not_applicable`, a nie fałszywe „pass”.

Tabela `sources` (zarządzana przez scraper, edytowalna z dashboardu):
`id, name, platform, url, source_kind, target_modules ["M1","M2","M3"], schedule_cron, active, last_run_at`.

## 4. Kontrakt: `Finding` (analityka → baza → API)

Jeden dokument może dać 0–3 findingi (po jednym na moduł).

```jsonc
{
  "id": "uuid",
  "document_id": "uuid",
  "module": "M1|M2|M3",
  "score": 0.87,                        // surowy wynik 0–1; próg NIE jest zapisywany – stosuje go API/dashboard
  "status": "new|in_review|confirmed|false_positive|closed",
  "title": "Reklama XTB przez finfluencera @inwestor_jan bez oznaczenia",
  "summary": "2–3 zdania uzasadnienia po polsku",
  "firm": {                             // firma inwestycyjna, której dotyczy materiał (M1, M2)
    "name": "X-Trade Brokers DM S.A.",
    "registry_id": "uuid | null",
    "registry_type": "dom_maklerski|bank_maklerski|oddzial_zagr|zagr_bez_oddzialu|null",
    "authorized": true,
    "match_confidence": 0.93
  },
  "advertiser": {                       // podmiot reklamujący / oferujący (M1, M3)
    "name": "Jan Kowalski",
    "handle": "@inwestor_jan",
    "profile_url": "https://...",
    "in_registry": false
  },
  "rules": [                            // M2: 18 reguł UKNF; M1/M3: sygnały
    {
      "rule_id": "R3",
      "name": "Informacja o ryzyku",
      "result": "fail|pass|not_applicable|uncertain",
      "severity": "high|medium|low",
      "evidence": "dokładny cytat z dokumentu",
      "evidence_locator": { "viewport": "desktop", "bbox": [0,0,0,0] },
      "explanation": "Obietnica zysku 20% bez ostrzeżenia o ryzyku w pobliżu.",
      "legal_basis": "art. 44 ust. 2 lit. b rozp. del. 2017/565"
    }
  ],
  "content_excerpt": "fragment treści do tabeli",
  "url": "https://...",                 // denormalizacja dla dashboardu
  "platform": "instagram",
  "detected_at": "2026-11-21T14:06:10Z",
  "updated_at": "2026-11-21T14:06:10Z",
  "model": { "pipeline_version": "0.3.0", "llm": "gemma3:4b", "embedder": "bge-m3" }
}
```

`risk_level` liczy API z progu: `high` ≥ próg modułu, `medium` ≥ próg − 0.2, reszta `low`.

## 5. REST API (API → dashboard)

Bazowy URL `/api`, JSON, paginacja `?page=1&page_size=50`.

| Metoda | Ścieżka | Opis |
|---|---|---|
| GET | `/findings` | lista; filtry: `module, status, platform, source_id, risk_level, score_min, date_from, date_to, q` |
| GET | `/findings/{id}` | szczegóły + `document` (tekst, linki, url screenów) |
| PATCH | `/findings/{id}` | `{ "status": "...", "note": "..." }` – zmiana statusu (wymóg alertowania) |
| GET | `/stats/trend` | `?module&bucket=hour|day&date_from&date_to` → `[{ "t": "...", "M1": 3, "M2": 7, "M3": 1 }]` |
| GET | `/stats/summary` | liczniki per moduł / status / platforma |
| GET | `/calibration` | `?module=M2` → krzywa: `[{ "threshold": 0.5, "tp": 12, "fp": 4, "fn": 2, "tn": 30, "precision": 0.75, "recall": 0.86 }]` |
| GET / PUT | `/settings/thresholds` | `{ "M1": 0.6, "M2": 0.5, "M3": 0.7 }` – zmiana progu przelicza `risk_level` |
| GET / POST / PATCH | `/sources` | lista i edycja źródeł |
| POST | `/scans` | `{ "source_id": "..." }` – ręczne uruchomienie skanu (XADD do `iw:scan-requests`) |
| GET | `/documents/{id}/screenshot/{viewport}` | podgląd screena z MinIO |
| GET | `/health` | stan serwisów (do demo) |

Kalibracja: TP/FP/FN liczone z findingów oznaczonych przez analityka (`confirmed` / `false_positive`) oraz ze **zbioru wzorcowego** (próbki UKNF + nasze etykiety, tabela `gold_labels`). Dzięki temu suwak progu na żywo pokazuje zmianę precyzji i pełności.

## 6. Zdarzenia czasu rzeczywistego

Redis Pub/Sub `iw:events` → API → Socket.IO (namespace `/events`):

| Zdarzenie | Payload | Kiedy |
|---|---|---|
| `finding.created` | `{ id, module, score, title, url, platform }` | każdy nowy finding |
| `finding.high_risk` | jw. | `score` ≥ aktualny próg modułu → toast/alert |
| `finding.updated` | `{ id, status }` | zmiana statusu (sync między kartami) |
| `scan.started` / `scan.finished` | `{ source_id, documents }` | pasek postępu skanu |

## 7. Konwencje wspólne

- Czas zawsze UTC ISO-8601; identyfikatory UUID v4 generuje producent rekordu.
- Konfiguracja tylko przez zmienne środowiskowe (`.env`, w repo tylko `.env.example`): `DATABASE_URL, REDIS_URL, MINIO_*, OLLAMA_URL, LLM_MODEL, EMBED_MODEL, PROXY_LIST, USER_AGENTS_FILE`.
- Migracje bazy w jednym miejscu (`/api/migrations`, Alembic) – A i C nie tworzą tabel ręcznie.
- Każdy serwis: `/health`, logi JSON na stdout, zero `console.log` w buildzie produkcyjnym frontendu.
- Zależności: `npm audit` / `pip-audit` przed każdym merge do `main`; wyniki do `doc/security-audit.md`.
- Gałęzie: `scraper/*`, `dashboard/*`, `analytics/*`; merge do `main` tylko z działającym `docker compose up`.

## 8. Kamienie milowe integracji

Termin oddania: **niedziela 22.11, 11:00**. Bufor: oddajemy o 10:30.

| Kiedy | Kamień | Dowód |
|---|---|---|
| sob. 14:30 | **Kontrakty v1 zamrożone** | `/contracts/*.schema.json`, mocki `findings.json`, `documents.json`; docker-compose z postgres/redis/minio/ollama wstaje |
| sob. 17:00 | **Integracja #1 – „cienka nitka”** | A wrzuca 1 prawdziwy dokument → C tworzy finding (nawet regułowo) → B widzi go w tabeli i dostaje alert WS |
| sob. 22:00 | **Integracja #2 – wszystkie moduły** | po ≥ 1 źródle dla M1, M2, M3; filtry, trend, zmiana statusu działają na prawdziwych danych |
| ndz. 03:00 | **Integracja #3 – kalibracja** | suwak progu zmienia FP/FN na zbiorze wzorcowym; harmonogram skanuje cyklicznie |
| ndz. 08:00 | **Feature freeze** | tylko poprawki; audyt zależności, README, czysta konsola |
| ndz. 10:30 | **Oddanie** | repo, PDF, README, film (opcjonalnie) |

Przy każdym kamieniu 10-minutowy sync całej trójki: co działa end-to-end, co blokuje, czy zmieniamy kontrakt.
