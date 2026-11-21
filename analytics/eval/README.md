# Gold set and evaluation

`gold.jsonl` is the labeled set the evaluation runs on. Each run computes precision, recall and F1 per module and per rule or signal, and gives the calibration panel its curve (`calibration_points`, read by `GET /api/calibration`). The spec is `openspec/changes/analytics-eval-calibration/specs/gold-set-evaluation/spec.md` (after archive: `openspec/specs/gold-set-evaluation/spec.md`), the decision record is ADR 0312.

```bash
python analytics/eval/run.py                 # report only, rules-only, no database
python analytics/eval/run.py --db            # also store the run (DATABASE_URL)
python analytics/eval/run.py --module M2     # one module
```

In the stack, the one-shot service `analytics-eval` runs `--db` on every `docker compose up` and writes a run only when the gold set, the pipeline version or the results changed.

## What the numbers mean

- **Module curve:** a document labeled for a module is a positive or a negative. Its score is that module's finding `score`, or 0 when the pipeline made no finding for the module. Counting follows the API exactly: positive prediction is `score >= threshold`, precision 1.0 when nothing is predicted positive, recall 0.0 without positives, 3 decimals.
- **Per rule or signal:** gold `fail` is a positive, `pass` a negative, `not_applicable` is left out of the counts. Two readings are reported. **`strict` is the headline number in the README and slides:** `uncertain` counts as not flagged, so it measures what the rules decide alone. `review` counts `uncertain` as flagged, which is what an analyst sees as "do weryfikacji".
- A rule switched off in its catalogue is `not_implemented`. A known stage-2 id that this build has no catalogue entry for is `not_in_build`. Both keep their labels, so the numbers appear as soon as the rule lands.
- A module with labels that produced no finding at all is `not_run`. It gets no stored rows, and the run exits 1.

This is our gold set, not UKNF's. It measures how well the rules follow our reading of the challenge criteria, written down label by label. It is not a measure of real-world prevalence.

## Labeling rules

1. **Labels come from the criteria, never from the current output.** M2 labels come from the operational description of each rule in `doc/ZASÓB … kryteria oceny informacji o ryzyku.docx`. M1 labels come from the Moduł 1 scope in `doc/Opis Wyzwania HackNation UKNF 19.11.pdf` §2. M3 labels come from annex 3 (art. 76 advice: a recommendation to buy, sell or hold instruments from art. 2, based on the client's situation). Write the label first, run the evaluation second. When a rule disagrees, record it in the change's `follow-ups.md` as a rule follow-up. Never change the label to match.
2. **`fail` means the problem is there.** For M2 that is a violation of the rule. For M1/M3 it is the signal being present (for example S1.2: an affiliate link is there).
3. **Document label:** `positive` means the module should flag it. For M2 that is a material with at least one violation. For M1 it is a third-party ad of a registered firm. For M3 it is a likely unauthorized advisory offer. Paid buy/sell signals sent to every subscriber are not tailored to one client's situation (art. 76), but annex 3 sums advice up as "rekomendacje nabywania, zbywania albo trzymania instrumentów finansowych", so they are labeled positive and marked as hard cases. `negative` means it should not be flagged.
4. **Partial rule labels are fine.** Label only the rules you are sure about. An omitted rule is not scored on that document. Use `not_applicable` when the rule cannot apply, for example the visual rules R4-R8 and R13 on a social post without `blocks`.
5. **`basis`** names the criterion the line was written from (for example `ZASÓB R3 (art. 44 ust. 2 lit. b)`). **`hard_case`** says in one sentence what makes the line hard, and is present only on hard cases. About a third of each module's lines are hard cases.
6. **`origin`**: `synthetic` for lines written here; `zasob-example` for lines built around a phrasing that ZASÓB quotes itself (R18's "Nasza inwestycja jest w pełni bezpieczna – spełniamy rygorystyczne wymogi nadzorcze KNF", R6's "sekcja Legal"); `uknf-sample` for official sample materials. **No official sample set was available:** Damian confirmed that `doc/` (the challenge PDF, ZASÓB and the three annexes) is everything UKNF provided, with no separate pendrive data, so the set is synthetic plus ZASÓB examples. If samples arrive, add them as ordinary `uknf-sample` lines after removing personal data: no code change is needed, and the report counts lines by origin.

## Privacy and fictional names

- Registered firms exist only in `registry.csv` next to this file: Zentrovia DM, Bank Kwarcowy BM, Nordavik Markets, Maltavera Trading, Lunaris DM. None of them shares a name, alias or domain with `analytics/registry/` (tested). Unregistered M3 entities (Aurum Horizon, Meridian Wealth, Kapitał Plus Doradcy and others) are invented too, with `*.example.*` domains.
- Domains are `*.example.pl` or `*.example.com`. Platform URLs are `*.example.com`.
- No real person's name, photo, phone number or address. Phone numbers are `+48 000 …` only (tested).
- Every `author.handle` in the gold set is one of these fictional handles (tested):

- `@etf_ziomek`
- `@fx_mentor_pl`
- `@gieldowy_kot`
- `@global_swing_desk`
- `@krypto_rakieta`
- `@kwarcowybm`
- `@ostrozny_inwestor`
- `@portfel_na_luzie`
- `@pytajacy_nowicjusz`
- `@spokojny_portfel`
- `@sygnaly_gpw_pro`
- `@trader_bez_kawy`
- `@wig20_snajper`
- `@zentroviadm`

## Adding a line

Write one JSON object per line: `{"id", "origin", "basis", "hard_case"?, "document": ScrapedDocument v1, "expect": {"M2": {"label", "rules": {"R3": "fail"}}}}`. The `id` is a unique slug such as `m2-r3-risk-far-from-claim`. The `document.id` must be a UUID v4, unique in the file. Then run `python analytics/eval/run.py`. A typo in a rule id, label or module stops the run with exit 2 and the line number.
