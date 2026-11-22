# Follow-ups

## Evaluation (rules-only, `eval/run.py --module M2`, gold 35 labeled M2 samples)

| Run | M2 at 0.1: P / R / F1 (tp fp fn tn) | best threshold |
|---|---|---|
| baseline `origin/main` 62f1a475 | 0.944 / 0.739 / 0.829 (17 1 6 11) | 0.1 |

## Items

| Item | Disposition |
|---|---|
| R5 "przesłonięcia przez inne elementy": the renderer reports no overlap between blocks, so occlusion by a banner or a cookie layer is not checked | new-item (renderer: an `occluded` flag per block) |
