# Presentation: analytics section (M1/M2/M3, calibration, extensibility)

Slide content for the hand-in PDF (issues #77 and #74). Kacper pastes it into the deck; each `##` below is one slide, with speaker notes under **Notes**. Written by Damian.

Numbers come from gold-set evaluation runs on `main` at `61238394` (2026-11-22 05:10 UTC, all 18 M2 rules), gold set SHA-256 `963f834e…`, pipeline 0.1.0:

- **rules only:** `python analytics/eval/run.py`, no LLM, no database;
- **with LLM:** `python analytics/eval/run.py --llm`, hosted DeepSeek Flash (`deepseek-flash`), run twice. M1 and M3 gave the same numbers both times. M2 did not: the LLM is not deterministic, so the slides give both M2 runs (run A, run B).

Per-rule and per-signal numbers are rules-only (`strict`). Thresholds are the hand-in defaults M1 0.75, M2 0.05, M3 0.4. To refresh them: rerun both commands and copy the `at_default_threshold` block (or the matching `points` entry) of each module and the `strict` block of each rule.

**The gold set is synthetic.** 69 documents written by us from the challenge criteria (67 `synthetic`, 2 built around phrasings that ZASÓB quotes itself), with fictional firms and handles. It measures how well the rules follow our reading of the criteria, not real-world prevalence. UKNF provided no sample ads (`doc/` is everything); no real samples will arrive before the hand-in (#73, closed as not planned). Real samples could later go in as `origin: uknf-sample` lines with no code change.

---

## 1. Three questions, three modules

One pipeline, routed by who published the material and whether the firm is in the KNF register (749 firms loaded from four KNF lists).

| Module | Question | Runs when | Output |
|---|---|---|---|
| **M1** finfluencers, third parties | Does someone other than the firm advertise a registered firm or its services? | third-party content mentions a registered firm | firm, advertiser, content, URL |
| **M2** risk-information compliance | Does a firm's own marketing meet art. 44 of Delegated Regulation 2017/565 (the 18 ZASÓB rules)? | the firm's own site or account | per-rule pass/fail with a verbatim quote |
| **M3** unauthorized advice | Does an entity outside the register offer what is in fact investment advice (art. 76)? | entity not in the register + advisory signals | entity, offer, URL |

**Notes:** Rules first, LLM second. Anything that can be checked deterministically (regex, dictionaries, render metadata of blocks) runs without a model; the LLM only decides cases the rules explicitly defer, and every LLM verdict must quote the document verbatim or it becomes "do weryfikacji". If the LLM is down, findings are rules-only.

---

## 2. M1: third-party ads of registered firms

Seven weighted signals, `score = σ(bias + Σ weight · signal)`:

- **S1.1** registered firm mentioned (name, alias or domain, fuzzy match)
- **S1.2** affiliate link or promo code (`?ref=`, `utm_`, "z moim linkiem") — weight 2.5
- **S1.3** partnership label (#reklama, #współpraca, `rel=sponsored`) — weight 2.0
- **S1.4** call to action ("otwórz konto", "link w bio") — rules, every hit confirmed by the LLM
- **S1.5** promotional vs. educational tone — LLM, 3 classes with a quote
- **S1.6** author is not the firm (handle and domain checked against the register)
- **S1.7** aimed at Polish audiences

**Gold set (synthetic, 18 docs, 9 hard cases), threshold 0.75:**

| Run | Precision | Recall | F1 | TP / FP / FN / TN |
|---|---|---|---|---|
| with DeepSeek Flash | **1.00** | **1.00** | **1.00** | 10 / 0 / 0 / 8 |
| rules only | 1.00 | 0.70 | 0.82 | 7 / 0 / 3 / 8 |

**Notes:** Strongest per-signal results rules-only: S1.1 F1 0.97, S1.6 F1 1.00, S1.7 F1 0.95. S1.5 is LLM-only by design, so rules-only it never decides on its own (strict recall 0); it shows up as "do weryfikacji" for the analyst. That is where the LLM adds recall on M1. Rules-only, the best F1 is at 0.4-0.65 (P 1.00, R 0.80, F1 0.89).

---

## 3. M2: 18 UKNF rules on risk information

Each rule is a class plus a YAML catalogue entry (name, severity, legal basis, dictionaries). Visual rules read render metadata of page blocks (font size, region, viewport); on social posts without blocks they are `not_applicable`.

- All 18 of 18 rules implemented: **R1** firm identification, **R2** ad label, **R3** risk next to return claims, **R4** risk font size, **R5** risk prominence and contrast, **R6** risk hidden in footer/footnotes, **R7** risk one click away, **R8** risk visible on mobile, **R9** plain language (LLM-first), **R10** language consistency, **R11** product comparisons, **R12** past performance (two sub-checks: R12a period and scope, R12b currency and costs), **R13** past performance dominating the message, **R14** past-performance disclaimer, **R15** forecasts, **R16** tax information, **R17** implying KNF approval, **R18** supervision as a safety argument.
- `score = Σ weight·fail / Σ weight·applicable`, high-severity rules weigh 3.
- **R9 is LLM-first:** rules-only it never fails, and its `uncertain` does not count to the score (`llm_only_uncertain`), so a rules-only finding is not diluted by a check only the model can decide.

**Gold set (synthetic, 35 docs, 14 hard cases), threshold 0.05:**

| Run | Precision | Recall | F1 | TP / FP / FN / TN |
|---|---|---|---|---|
| with DeepSeek Flash, run A | **1.00** | **0.96** | **0.98** | 22 / 0 / 1 / 12 |
| with DeepSeek Flash, run B | 0.92 | 0.96 | 0.94 | 22 / 2 / 1 / 10 |
| rules only | 0.95 | 0.91 | 0.93 | 21 / 1 / 2 / 11 |

| Rule | Precision | Recall | F1 | Gold fails |
|---|---|---|---|---|
| R1 | 1.00 | 1.00 | 1.00 | 1 |
| R2 | 1.00 | 0.67 | 0.80 | 3 |
| R3 | 0.78 | 1.00 | 0.88 | 7 |
| R4 | 1.00 | 0.50 | 0.67 | 2 |
| R5 | 1.00 | 1.00 | 1.00 | 2 |
| R6 | 1.00 | 1.00 | 1.00 | 2 |
| R7 | 1.00 | 1.00 | 1.00 | 1 |
| R8 | 1.00 | 1.00 | 1.00 | 3 |
| R9 | 1.00 | 0 | 0 | 1 |
| R10 | 1.00 | 1.00 | 1.00 | 1 |
| R11 | 1.00 | 1.00 | 1.00 | 1 |
| R12a | 1.00 | 1.00 | 1.00 | 1 |
| R12b | 1.00 | 1.00 | 1.00 | 2 |
| R13 | 1.00 | 1.00 | 1.00 | 1 |
| R14 | 1.00 | 1.00 | 1.00 | 1 |
| R15 | 1.00 | 1.00 | 1.00 | 1 |
| R16 | 1.00 | 1.00 | 1.00 | 1 |
| R17 | 1.00 | 0.33 | 0.50 | 3 |
| R18 | 1.00 | 1.00 | 1.00 | 2 |

**Notes:** With all 18 rules built, rules-only recall rose from 0.74 to 0.91. The default moved from 0.1 to 0.05 because one failing rule now weighs less in `Σ weight·fail / Σ weight·applicable` (ADR 0319); at the old 0.1 rules-only recall would be 0.83. The LLM adds recall where the rules defer: R9 (rules-only recall 0 → 1.00 with DeepSeek) and R17 (0.33 → 1.00 in run A, 0.67 in run B). Run B also had 2 false positives that run A did not, so the LLM's precision on M2 is 0.92-1.00 between runs. Per-rule counts are small (1-7 fails each), so read them as "the rule behaves as specified", not as a statistic.

---

## 4. M3: shadow investment advice

Art. 76 advice = a recommendation to buy, sell or hold specific instruments, based on the client's situation. Signals:

- **S3.1** entity not in the KNF register
- **S3.2** advisory vocabulary (wealth management, "indywidualna strategia")
- **S3.3** personalization ("dopasujemy do Twojej sytuacji", 1:1) — rules + LLM
- **S3.4** recommendation of a specific instrument (buy/sell/hold + share, bond, ETF, CFD…) — rules + LLM, weight 3
- **S3.5** paid signals, VIP group · **S3.6** aimed at Poland · **S3.8** crypto only (outside art. 2, capped)

**Hard gate:** without S3.4 the score is capped at 0.4. Education or personalization alone is not advice.

**Gold set (synthetic, 18 docs, 11 hard cases), threshold 0.4:** precision **1.00**, recall **0.40**, F1 **0.57** (TP 4, FP 0, FN 6, TN 8), the same with DeepSeek Flash and rules only.

**Notes:** The default threshold is deliberately the gate cap (0.4), not the best-F1 point (rules only at 0.25: P 0.86, R 0.60, F1 0.71; with DeepSeek at 0.25: P 0.71, R 0.50, F1 0.59). We prefer no false accusations of unauthorized activity over recall. S3.3 and S3.4 are the LLM-backed signals; rules-only they only mark candidates "do weryfikacji", which is why rules-only recall is low. M3 has the most hard cases (paid signals sent to all subscribers, "education" that names instruments).

---

## 5. Calibration: thresholds are measured, not chosen

- Every `docker compose up` runs the evaluation once and stores the threshold curve; the dashboard's calibration panel shows it, plus the labels analysts add from the alert view.
- Default thresholds are measured on the gold set ([ADR 0316](decisions/0316-default-thresholds-from-evaluation.md), [ADR 0318](decisions/0318-hosted-llm-deepseek-flash.md), [ADR 0319](decisions/0319-m2-default-threshold-005.md)): M1 0.75 (best F1 with DeepSeek Flash, plateau 0.75-0.80), M2 0.05 (best F1 rules-only and with DeepSeek, the only point on the plateau), M3 0.4 (the S3.4 gate cap). M2 is low by design: its score is the weighted share of failing rules among the applicable ones, so every rule that applies and passes lowers the score of a material with one real violation; the old 0.1 would miss 2 more positives (rules-only, ADR 0319). A rule or gold-set change that moves them fails a test until they are re-measured.
- Moving the M2 threshold (demo):

| M2 threshold | Precision (rules / DeepSeek A / B) | Recall (rules / DeepSeek) | F1 (rules / DeepSeek A / B) | Alerts (TP+FP, rules / DeepSeek A / B) |
|---|---|---|---|---|
| 0.05 (default) | 0.95 / 1.00 / 0.92 | 0.91 / 0.96 | 0.93 / 0.98 / 0.94 | 22 / 22 / 24 |
| 0.10 | 0.95 / 1.00 / 0.91 | 0.83 / 0.87 | 0.88 / 0.93 / 0.89 | 20 / 20 / 22 |
| 0.25 | 1.00 | 0.61 | 0.76 | 14 |
| 0.40 | 1.00 | 0.30 | 0.47 | 7 |

**Notes:** Gold set: 69 synthetic documents, about a third hard cases by design, labels written from the criteria before running the rules (a disagreement becomes a rule follow-up, never a relabel). From 0.25 up, all three runs give the same numbers. The numbers are honest about what is missing: no real samples, R9 scores only with the LLM, the LLM is not deterministic (M2 precision 0.92-1.00 over two runs), and the LLM numbers are for one hosted model (DeepSeek Flash); local Gemma is not measured on the gold set.

---

## 6. Open for extension: a new rule in two files

Real example: **R14** (past performance needs a "results are not a reliable indicator" disclaimer), commit `45bd8fee`. No change to the pipeline, scoring, contracts, API or dashboard.

**1. Catalogue entry** — `analytics/src/investwatch_analytics/rules/m2_rules.yaml` (shortened; the real entry has ~40 lines of patterns):

```yaml
  - id: R14
    name: Ostrzeżenie przy wynikach historycznych
    severity: high
    legal_basis: art. 44 ust. 4 lit. d rozp. del. 2017/565
    implemented: true
    params:
      figure_patterns:   ['\d+(?:[.,]\d+)?\s?%']
      past_patterns:     ['\bhistoryczn\w*', '\bwypracowa(?:ł|ła|ło|li|ły|liśmy)\w*', …]
      future_patterns:   ['\bprognoz\w*', '\bbędzie\w*', …]
      disclaimer_patterns:
        - '\bwynik\w*\s+historyczn\w*\b.{0,80}?\bnie\s+(?:są|jest|stanowi\w*|gwarantuj\w*)'
```

**2. Rule class** — `analytics/src/investwatch_analytics/rules/m2.py` (shortened from the 52 added lines; pattern compilation and the footnote check left out):

```python
@register
class R14PastPerformanceDisclaimer(Rule):
    rule_id = "R14"

    def evaluate(self, ctx: Context) -> RuleResult:
        claims = [s for s in ctx.pre.sentences if self._is_past_performance(s.text, ctx.doc.fetched_at.year)]
        if not claims:
            return self.result("not_applicable", None, "Materiał nie prezentuje wyników historycznych.")
        if not any(d.search(s.text) for s in ctx.pre.sentences for d in self._p["disclaimer"]):
            return self.result("fail", claims[0].text,
                "Wyniki historyczne bez wyraźnego zastrzeżenia, że nie są wiarygodnym wskaźnikiem przyszłych wyników.")
        return self.result("pass", ..., "Materiał zawiera zastrzeżenie dotyczące wyników historycznych.")
```

Plus one line registering the new parameter names (`engine.py`, so a typo in the YAML fails at load) and unit tests.

**What you get for free:** the rule shows up in findings with its quote and legal basis, is weighted into the M2 score by its severity, is scored by the next gold-set run (its labels were already there), and appears in the dashboard. Tuning a dictionary is a one-line YAML change with no code.

**Real diff size** (`git show --stat 45bd8fee`): +52 lines Python, +44/−3 YAML, +2 engine, +129 test lines (117 of them a new test file).

**Optional LLM hook:** add an `llm:` block (`question`, `when: uncertain`) to the catalogue entry and the engine sends the model only the cases the rule defers: `when: uncertain` sends only doubtful verdicts (R3, R18), `when: always` every case where the rule applies (R17).

---

## 7. Open model: hosted DeepSeek Flash or local Gemma, by env only

The LLM is any OpenAI-compatible endpoint, set in the root `.env`. Hosted model for the hand-in: DeepSeek Flash (`LLM_BASE_URL=https://api.deepseek.com`, `LLM_MODEL=deepseek-flash`). Swap target: the open model `gemma3:4b` in Ollama on the same machine (`--profile llm`). No provider SDK; empty `LLM_BASE_URL` means rules-only.

Measured with DeepSeek Flash: on the gold set, 28 calls, all HTTP 200, no timeouts or malformed answers, latency p50 2.4 s / p95 6.4 s. On the stack with real pages, a second pass over the same 7 documents made 0 LLM calls and gave the same scores (cache). With a wrong API key, DeepSeek answered 401, the verdicts were dropped and the finding was rules-only, with the deferred checks left "do weryfikacji".

Runbook (`analytics/README.md`, "LLM: hosted Gemma or local Ollama", PR #69), on the demo machine:

1. In `.env`, comment out the hosted lines and set
   `LLM_BASE_URL=http://ollama:11434/v1`, `LLM_MODEL=gemma3:4b`, `LLM_API_KEY=ollama`,
   the slower local limits `LLM_TIMEOUT_S=240`, `LLM_DOC_BUDGET_S=300`, `CLAIM_MIN_IDLE_MS=360000`, `LLM_CHUNK_CHARS=1500`, `LLM_MAX_CHUNKS=1`,
   and `EMBED_BASE_URL=http://ollama:11434/v1` for `bge-m3`.
2. Pull the models once (~4.5 GB): `docker compose --profile llm up --exit-code-from ollama-pull ollama-pull`.
3. Start: `docker compose --profile llm up -d` (stack already running: `docker compose --profile llm up -d ollama analytics`).
4. Check: `docker compose logs analytics | grep llm_mode` shows `local`; LLM-decided findings carry `model.llm = "gemma3:4b"`.
5. Back: restore the hosted lines, drop the local-only chunk limits, `docker compose up -d analytics`.

**Notes:** Safety nets: a failing endpoint opens a circuit breaker and findings stay rules-only (no automatic model switch); the worker refuses to start if `CLAIM_MIN_IDLE_MS` is not above the LLM budget; the cache key includes the model, so pages are re-analysed after a switch. `gemma3:4b` quality is not measured on the gold set; the published LLM numbers are DeepSeek Flash, next to the rules-only numbers. Rehearsed on the demo machine on 2026-11-22 (#74): the switch takes about 40 s and the switch back about 60 s. On CPU one local M1 verdict took 182 s against 4.6 s hosted, and the M2 call timed out, so locally most checks stay rules-only. Say so, and show one `model.llm = "gemma3:4b"` finding rather than a live local scan.
