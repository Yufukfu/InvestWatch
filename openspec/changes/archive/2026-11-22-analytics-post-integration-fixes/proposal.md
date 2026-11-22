# Proposal

## Why

Two end-to-end runs on real data (2026-11-21/22, `main` with the real KNF register #50, the eval-based thresholds #51/#64 and the hosted Gemma 4 LLM layer #64) showed that M1, M2 and M3 work end to end. They also found three analytics defects:

1. **The supervisor became an advertiser.** The KNF public-warnings page (`www.knf.gov.pl/dla_konsumenta/ostrzezenia_publiczne`, a scraper seed) produced the M1 finding "knf.gov.pl wspomina EuroTrade…". The page names registered firms, so routing sent it to M1 with KNF as the advertiser. For any unregistered entity it warns about, the same page would be an M3 publisher.
2. **Vocabulary alone made an M3 finding.** The negative control `ey.com` (EY's family-office page; `scraper/seeds/sources.toml` says it "should NOT raise an M3 finding") produced M3 0.269 = σ(-3 + S3.1 0.5 + S3.2 1.0 + S3.6 0.5). That is an unregistered name, service vocabulary and a Polish page, with no offer at all. The mock `72acbb3b…`, a blog that explains family offices and says it gives no recommendations, gets the same 0.269 finding.
3. **Preprocessing repeats NFKC.** `preprocess` called `normalize`, and then `content_hash` and `guess_language` each normalized the whole text again. 2 MB of `ﬁ` took about 26 s. `main` has since dropped the NFKC `content_hash` (stored-hash change, `eaab7634`), which leaves two passes; this change makes it one.

The thresholds were measured rules-only (ADR 0316). With the LLM on, the numbers may move, and Damian decides whether the defaults change.

## What Changes

- **Official sources are not advertisers** (`modules/router.py`, `config.py`). A page whose host is a supervisor or official-register domain goes to no module, with the reason `official_source`, logged like the other skip reasons. The default list is `knf.gov.pl`, `uknf.gov.pl` and `gov.pl`, with their subdomains matched on a label boundary. `doc/` names only `knf.gov.pl` (the register links in the annexes), so the default list stops there. `OFFICIAL_SOURCE_DOMAINS` (comma-separated, env only) replaces it.
- **M3 needs an offer signal** (`modules/m3.py`). An M3-only document gets a finding only when S3.3 (personalization), S3.4 (recommendation of instruments), S3.5 (paid model) or S3.8 (crypto-asset calls) is `fail` or `uncertain`. S3.2 (service vocabulary), S3.1 and S3.6 still count in the score of an offer, but on their own they are no offer, so the result is `no_signals`. The M3-alongside-M1 rule (S3.3/S3.4) does not change.
- **NFKC once** (`preprocessing.py`). The text is normalized once, and the language is derived from that result. Sentences are still split on the original text, so offsets do not change.
- **Evaluation with the LLM.** `eval/run.py --llm` runs with hosted Gemma 4. For each module it reports P/R/F1 at the current defaults (M1 0.65, M2 0.1, M3 0.4), the best-F1 threshold, its plateau and the number of cases, and these go to the coordinator and Damian. **This change does not change the committed defaults.**

## Out of scope

- The following stay out: `pipeline.py` wiring (the `analytics-embeddings` change edits it), M2 P1 rules (`analytics-m2-p1-rules`), `web/`, `scraper/` and `contracts/`.
- The mocks (`contracts/mocks`, `contracts/mock-server`, `web/` fixtures) are not edited. The mock finding for `72acbb3b…` stays as a contract example of a capped M3 finding, and the difference is recorded in `follow-ups.md`.
- S3.7 (the KNF warnings list as a signal), changing default thresholds, and re-labelling the gold set.
- **Owner:** Damian (`analytics/`).
- **Contracts:** none. No contract, REST route or event changes. `official_source` is only a new log reason.
