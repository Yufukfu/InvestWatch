# Design

## 1. Module and registration

The rule classes live in `analytics/src/investwatch_analytics/rules/m2_visual.py` and register with `@register` like the other M2 rules. `Catalogue.load` imports the module next to `m1`, `m2` and `m3`. They reuse the block helpers of R4 and R6 from `rules/m2.py` (`_RiskWarnings` for the risk dictionary and the quote, `locate`, `locator_for`, `VIEWPORTS`, `weighted_median`) and the past-performance detector `_PastPerformance`, so a risk block or a past-performance sentence means the same thing in every rule. `rules/m2.py` itself changes only in the detector (decision 6), so the parallel text-rules change can add R9 and R10 there without conflicts.

## 2. Viewport verdicts

Each rule judges each rendered viewport (`desktop`, `mobile`, `tablet`), then reports the worst one (`fail` > `uncertain` > `pass`, desktop first on ties), as R4 and R6 do. Inside a viewport, R5 and R7 pass when at least one risk block is exposed: a page with a clear warning is not failed for a duplicate hidden in a menu. A missing field is never a pass: it gives `uncertain`, or `not_applicable` ("brak metadanych renderowania") when no risk block of any viewport has it.

## 3. R5 contrast

WCAG 2.x contrast ratio `(L1 + 0.05) / (L2 + 0.05)` from the relative luminance of `color` and `background_color` (`#rrggbb`, the renderer already flattens alpha). `min_contrast` is 4.5, the WCAG AA level for normal text. We do not lower it to 3:1 for large text: ZASÓB R5 checks contrast and legibility of the warning itself, and a risk warning is typically body-size text, so one threshold keeps the verdict simple to explain. `visible: false` fails R5 (R4 leaves invisible blocks to R5). The displayed ratio is truncated so it never contradicts the verdict.

## 4. R7 and R8

R7 reads only `requires_interaction`. R8 checks every rendered viewport: if a viewport has no visible risk block while another viewport has a risk block, the warning is missing there. Otherwise its best visible risk block must have `overflow_clipped` not `true` and `font_size_px >= min_font_px` (12 px, applied to every viewport: ZASÓB names desktop, tablet and phone). `overflow_clipped: null` is unknown. With one rendered viewport R8 cannot compare devices: a defect still fails, a clean single viewport is `uncertain`.

## 5. R13 dominance

A block presents past performance when it contains a detector sentence, or when it shows a return figure (`pp_figure`) that a detector sentence of the document also states: a headline `+120% w 5 lat!` restating `łączna stopa zwrotu 120%` is past performance. In a viewport, among visible blocks with a positive size, a past-performance block dominates when its font is the largest (ties included), or when it is the first block (smallest `bbox` y, else block order) and its font is above the length-weighted median size. Evidence is the block text located in the document text.

## 6. Detector: closed year ranges

`_PastPerformance.is_past_performance` treats a year range `YYYY-YYYY` (hyphen or dash) whose end year is at or before the fetch year as a past marker, after the future and forecast markers, exactly like a single past year. One detector stays shared by R12a, R12b, R14 and R13 (ADR 0315). This changes R14's verdict on gold `m2-r13-past-performance-dominates` from `not_applicable` to `pass`, which its label expects.

## 7. Evaluation

Gold already labels R5, R7, R8 and R13 on every visual example. The rules-only run is compared before and after (tasks group 6). If the recommended M2 threshold moves, `test_eval_thresholds` is left failing and the numbers go to the coordinator: the default thresholds belong to another branch.
