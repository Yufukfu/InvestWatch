# Evidence: the real KNF register pages

Read-only fetches on 2026-11-21 (UTC evening) with `curl` and a browser user agent, at most 2 requests per second. Nothing was posted, and no login was involved. The raw pages are not committed by this planning change; implementation saves trimmed snapshots as test fixtures (tasks group 1).

## Sources

`doc/Załącznik do Tematu 1 Wyzwanie KNF HackNation.docx` and `doc/Załącznik do Tematu 2 …docx` link the same five URLs (checked in `word/_rels/document.xml.rels` of both files). Base: `https://www.knf.gov.pl/podmioty/Podmioty_rynku_kapitalowego/Firmy_inwestycyjne_i_Agenci_firm_inwestycyjnych`.

| List | Path under the base | HTTP | Size | Records | Pages |
|---|---|---|---|---|---|
| Summary ("Rejestr Firm Inwestycyjnych") | (the base itself) | 200 | 62 KB | 0: links only | 1 |
| Banks conducting brokerage activity | `/Banki_prowadzace_dzialalnosc_maklerska` | 200 | 88 KB | 10 | 1 |
| Brokerage houses | `/domy_maklerskie` | 200 | 111 KB + 84 KB | 20 + 8 = 28 | 2 |
| Branches of foreign investment firms (EU/EEA) | `/notyfikowane_firmy_inwestycyjne_oddzialy` | 200 | 109 KB | 10 | 1 |
| Foreign investment firms without a branch (EU/EEA) | `/notyfikowane_zagraniczne_firmy_inwestycyjne` | 200 | 145-182 KB each | 35 × 20 + 12 = 712 | 36 |

Total: 760 records, 753 distinct names after the duplicates below.

## Format

- **Server-rendered HTML only.** The site is a Next.js app (`/_next/static/chunks/…`), but the records are in the initial HTML; no JavaScript is needed. No XLSX, CSV, JSON or API link exists on any of the five pages. The only downloads are a PDF legend of the activity codes (`Zakres_dzialalnosci_…_91227.pdf`) on the domestic lists.
- **One `<table>` per firm**, inside `<div id="entityTable" … data-entities-type="supervised|notified">`. Each table has rows of `<th scope="row">label</th><td>value</td>`. The table classes are Tailwind utility classes (`rounded-default tooltip-table-parent`), so the loader keys on the `#entityTable` container and the `th` label text, not on classes.
- **Encoding:** UTF-8 (`content-type: text/html; charset=utf-8`), no replacement characters in any page; Polish diacritics are intact (`Zakres działalności`, `ŚLĄSKI`).
- **Pagination:** `?page=N` links, 20 records per page. A page beyond the last returns HTTP 200 with the last page's records (`?page=99` of the no-branch list equals `?page=36`). The loader therefore stops when a page adds no new record and caps the page count; it never relies on a 404.
- **robots.txt:** `User-agent: * Allow: /`.
- **No "last updated" date** on the list pages.

### Fields per list (the `th` labels, verbatim)

| List | Labels |
|---|---|
| Brokerage houses, banks (`supervised`) | `Nazwa`, `Dane Teleadresowe`, `Data zezwolenia`, `Zakres działalności` |
| Branches (`notified`) | `Nazwa podmiotu`, `Adres siedziby`, `Państwo macierzyste`, `Organ nadzoru`, `Data wpisu do KRS` (9 of 10), `Instrumenty finansowe (C)`, `Usługi inwestycyjne (A)`, `Usługi dodatkowe (B)` (5 of 10), `Dane teleadresowe oddziału w Polsce - adres`, `… - telefon`, `Data wpływu zawiadomienia` |
| No branch (`notified`) | `Nazwa podmiotu`, `Adres siedziby`, `Państwo macierzyste`, `Organ nadzoru`, `C - Instrumenty finansowe z sekcji C …`, `A - Usługi inwestycyjne …`, `B - Usługi dodatkowe …`, `Data wpływu zawiadomienia`, `Dodatkowe informacje` (278 of 712), `Za pośrednictwem agenta` (rare) |

What is **not** there:

- **No KNF identifier** (no register number, KRS, NIP or LEI) on any list. A stable id must come from the name.
- **No website field.** Domestic firms (brokerage houses, banks) have no domain at all. On the foreign lists, `Organ nadzoru` holds the supervisor's site (`www.cysec.gov.cy`, `www.bafin.de`, `www.afm.nl`, `www.cnb.cz`), which is not the firm's domain.
- `Dodatkowe informacje` (no-branch list) is free text. In 155 of 712 records it mentions domains and in 152 it names trade names, e.g. `nazwy handlowe: 50K, 50Coins www.50k.trade [od 10.05.2024] www.50coins.com …`, `Nazwy handlowe: AccurateFX XGLOBAL … www.xglobalmarkets.com`. It also holds non-name facts (`OTF: FTFS MTF: FTFS`).

### Names

- Domestic names are mostly upper case with the legal form: `AIXON INVESTMENT MANAGEMENT SP. Z O.O.`, `CVI DOM MAKLERSKI SP. Z O.O.`, `mBANK S.A. Biuro Maklerskie mBank`. A bank's record holds the bank and its brokerage unit on separate `<br>` lines: `ALIOR BANK S.A.` / `Biuro Maklerskie ALIOR Bank`; `POWSZECHNA KASA OSZCZĘDNOŚCI BANK POLSKI S.A. (PKO BP S.A.)` / `Biuro Maklerskie PKO Banku Polskiego` (an inflected form).
- **Former names in `<strike>`:** 6 on the brokerage list (`CERES DOM INWESTYCYJNY S.A.` with `<strike>EFIX DOM MAKLERSKI S.A.</strike>`), 3 on the banks list, 816 on the no-branch list (`42 financial services a.s.`, former `42 financial services s.r.o.`).
- **Markup artifact:** on the banks list a `<strike>` wraps only `<br />B`, so removing struck text naively turns `Biuro Maklerskie PEKAO` into `iuro Maklerskie PEKAO`. A struck run counts as a former name only when it covers a whole `<br>`-separated line.
- Foreign names carry many legal forms: `GmbH`, `AG`, `B.V.`, `a.s.`, `s.r.o.`, `Ltd`, `Limited`, `SAS`, `AS`, `S.A.`.
- Country (`Państwo macierzyste`) is a Polish country name (`Cypr` 8, `Niemcy` 4, `Holandia` 2 … on page 1), mapped to ISO 3166-1 alpha-2 by the loader. Domestic lists have no country field (all `PL`).

### Duplicates

- Within the no-branch list: 3 names appear twice (`EOS Venture`, `GBR Capital GmbH`, `Mariana UFP SAS`), compared case-insensitively.
- Across lists: 7 names are on both the branch list and the no-branch list (`CMC Markets Germany GmbH`, `Convera Europe Financial S.A.`, `EXT Ltd`, `IG Europe GmbH`, `Jefferies GmbH`, and 2 more).
- No empty names.

## Stability

- The format is a page layout, not a published dataset: KNF can change the markup at any time without notice (the site is a recent Next.js build; the legal note says the content and the service may change without warning). The `th` labels and the `#entityTable` id are the most stable anchors.
- The record count is the main drift signal: the committed CSV records the count per list, and a reload that loses more than half of a list's records fails instead of writing.

## Licence

KNF legal note (`https://www.knf.gov.pl/o_nas/urzad_komisji/nota_prawna`, updated 2017-06-23): reuse of material from the site requires naming the source with a link to `www.knf.gov.pl`; KNF takes no responsibility for errors. No other restriction. Lists of supervised firms are public-register information.

## KNF public warnings list (bonus, S3.7)

`https://www.knf.gov.pl/dla_konsumenta/ostrzezenia_publiczne`: HTTP 200, one 819 KB HTML page, 13 tables (`Lp.`, `Nazwa podmiotu, w związku z działalnością którego złożono zawiadomienie…`, `Numer identyfikujący podmiot (KRS, NIP lub REGON)`, `Właściwa prokuratura`, `Wzmianki o prawomocnych orzeczeniach…`, `Informacje istotne`), about 670 rows, no pagination, no download. Names are free text with numbered sub-entities, seats and platform domains in one cell (`1. Grand Marshall Ltd. z siedzibą w … (www.grandtrade.exchange) 2. …`). Domains are cheap to extract by regex; entity names are not (no stable separator). Kept out of scope (design, Non-goals).
