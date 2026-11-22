# Proposal

## Why

`main` implements 12 of the 18 UKNF ZASÓB rules. The renderer from `scraper-v3-render` (#67) now gives every rendered page per-viewport `blocks` with colours, visibility, interaction, clipping, font size and position, so the visual rules that waited for it can run on real pages. The jury scores against all 18 criteria. Damian approved the scope ("dokładamy brakujące reguły, start").

## What Changes

Four visual M2 rules, worded after `doc/ZASÓB DLA UCZESTNIKÓW - InvestWatch - kryteria oceny informacji o ryzyku.docx` (ZASÓB):

- **R5 Ekspozycja i kontrast ryzyka** (art. 44 ust. 2 lit. c i e; ZASÓB: "kontrastu, przesłonięcia przez inne elementy oraz czytelności"): a risk block with WCAG contrast below `min_contrast` (4.5:1) or `visible: false` fails; unknown colours are `uncertain`.
- **R7 Dostępność za 1 kliknięciem** (art. 44 ust. 2 lit. b i e; ZASÓB: "wymaga rozwinięcia, kliknięcia linku lub przejścia na inną warstwę"): a risk block with `requires_interaction: true` and no other reachable risk block fails.
- **R8 Responsywność** (art. 44 ust. 2 lit. g; ZASÓB: "czy tekst nie jest ucinany lub skalowany poniżej czytelności" on desktop, tablet and phone): the warning is missing in a rendered viewport, clipped, or below `min_font_px` (12 px).
- **R13 Dominacja wyników historycznych** (art. 44 ust. 4 lit. a; ZASÓB: "czy wyniki historyczne nie stanowią najbardziej wyeksponowanego elementu"): a past-performance block has the largest font of its viewport, or is the first block and above the dominant size.

All four: `not_applicable` without `blocks`, the worst viewport decides, `evidence_locator` names the block, and the evidence is a verbatim quote. The rule classes live in a new module `rules/m2_visual.py`.

The shared past-performance detector (R12a, R12b, R14 and now R13) also reads a closed year range (`2021-2025`) ending at or before the fetch year as a past marker; gold `m2-r13-past-performance-dominates` was not detected before.

## Out of scope

- R9 and R10 (text rules, a parallel change), and the default thresholds (branch `analytics/analytics-deepseek-default`).
- Occlusion by another element (R5 "przesłonięcia"): the renderer reports no overlap; a follow-up.
- Any contract, REST route or event: none is touched. `blocks` are read as `contracts/schemas/scraped-document.schema.json` defines them.

Owner: `analytics/` ([`.github/CODEOWNERS`](../../../.github/CODEOWNERS)).
