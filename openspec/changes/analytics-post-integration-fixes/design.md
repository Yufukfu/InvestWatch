# Design

## 1. Official sources

**Where.** The check is the first one in `modules/router.py` `route()`, before the publisher lookup, and it returns `Route(None, None, "official_source")`. For a `None` module, `pipeline.analyze` already logs `document skipped` with `r.reason`, so `pipeline.py` needs no edit (the embeddings change owns that file).

**Which host.** The check uses the page host (`http_host(doc.url)`) and, when it is present and not a social platform, the host of the author's `profile_url`. Links and mentions in the text never make a document official: a finfluencer who links to the KNF register is still a finfluencer. A host matches when it is equal to a listed domain or a subdomain of it on a label boundary, after the same `_normalize_domain` the registry applies to `website_domains`. So `knf.gov.pl.example.com` and `fakeknf-gov.pl` are not official.

**The list.** It holds `knf.gov.pl`, `uknf.gov.pl` and `gov.pl`. `gov.pl` already covers the two KNF hosts. They are listed anyway so that anyone who copies the default and drops `gov.pl` still sees them. `doc/` names only `knf.gov.pl`, in the five register links of the annexes to topics 1-3. It names no other supervisor or register host, so ESMA and foreign regulators are left to `OFFICIAL_SOURCE_DOMAINS`.

**Config** is env only, as the repo requires. `config.official_source_domains()` reads `OFFICIAL_SOURCE_DOMAINS` at call time, and an empty or unset value means the default. An invalid entry raises `ConfigError` naming the variable: one without a dot, or one with a scheme, a path, a port or a wildcard. `route()` takes an optional `official_domains` argument for tests.

**No module at all, not "M3 only".** The supervisor never advertises, makes offers or publishes its own marketing. M2 is excluded too, because no gov.pl host is in a registry firm's `website_domains`.

## 2. Minimum signal set for an M3 finding

ADR 0308 frames M3 as an offer that "may indicate" advice (the Opis says "oferty mogących wskazywać"). Under art. 76, the offer rests on S3.4 (instruments) and S3.3 (the client's situation). ADR 0308 rejected option 3 because "education and service vocabulary alone" must not reach the alert threshold. The spec's skip rule, though, counted S3.2 as an advisory signal. So vocabulary alone still created a finding below the threshold, on the EY page and on `72acbb3b…`, and neither should have one: the EY page is a negative control in sources.toml, and the blog says it gives no recommendations.

Options:

1. **Keep S3.2 in the set and rely on the threshold** (the status quo). Rejected: every page that names "family office" gets a finding row in the dashboard and in reports, including pages of authorized advisors and educational pages. `sources.toml` also says the controls must give no M3.
2. **Require an offer signal (chosen):** S3.3, S3.4, S3.5 or S3.8 `fail` or `uncertain`. Each one is part of an offer: what is recommended (S3.4, S3.8), to whom (S3.3) and for money (S3.5). S3.2, S3.1 and S3.6 say who speaks and where, not what is offered. The English advisory offer scenario (S3.2 + S3.5) still gives a finding, and so does a paid VIP crypto group (S3.5/S3.8).
3. **Require S3.3 or S3.4** (the art. 76 pair). Rejected: it drops paid signal groups whose S3.4 is still only a rule candidate, and the crypto calls (S3.8) that the spec wants reported, capped.

**Effect on the gold set** (rules-only, measured before the change). Three findings disappear:

- `72acbb3b…` (mock, 0.269)
- `m3-english-offshore-no-poland` (negative, 0.182)
- `m3-investment-consulting` (positive, 0.269; the rules miss its S3.3, S3.4 and S3.5)

All three are below the M3 default of 0.4, so P/R/F1 at the default do not change. The sweep below 0.27 can change.

## 3. NFKC once

`preprocess` computes `norm = normalize(text)` once and passes it to the private helpers `_hash_of_normalized(norm)` and `_language_of_normalized(norm)`. The public `content_hash(text)` and `guess_language(text)` stay, because other callers and tests use them. They become `normalize` followed by the private helper, so their results do not change. `split_sentences(text)` already runs on the original text.

Tests:

- **Equivalence:** compared with the field-by-field functions, on every mock and on seeded random texts.
- **Call count:** `unicodedata.normalize` is patched and must be called exactly once.
- **Growth:** 100k against 400k copies of `ﬁ`, compared as a ratio.

## 4. Evaluation with the LLM

The run is `python eval/run.py --llm` with:

- `LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai`
- `LLM_MODEL=gemma-4-31b-it`, falling back to `gemma-4-26b-a4b-it` on repeated 503 (the model used is recorded)
- the key from the untracked root `.env`, never printed

The report's numbers go to the coordinator. `eval/thresholds.json`, `events.DEFAULT_THRESHOLDS` and the API's `DEFAULTS` stay as committed until Damian decides.
