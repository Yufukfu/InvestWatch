# analytics

Owners: [`.github/CODEOWNERS`](../.github/CODEOWNERS).

Consumes the Redis Stream `iw:documents` (consumer group `analytics`), runs modules M1-M3, inserts `findings` and publishes to `iw:events`. The logic lives in the docs, not here:

- Pipeline, rules and LLM layer: [`.docs/analytics-plan.md`](../.docs/analytics-plan.md) §2 (pipeline), §4-6 (M1-M3), §7 (LLM), §8 (evaluation and calibration).
- Input contract `ScrapedDocument`: [`.docs/integration-plan.md`](../.docs/integration-plan.md) §3. Output `Finding`: §4. Events: §6.

## Rules that are easy to get wrong

- Rules before LLM. Anything checkable deterministically (regex, dictionaries, block metadata) runs without a model.
- Every LLM result needs an evidence quote that is verified as a substring of the document; otherwise the result is `uncertain`, not `fail`.
- Degrade, don't fail: if the LLM endpoint is down the pipeline runs rules-only and records `model.llm = null`.
- Store the raw `score` (0-1) on the finding; never compute `risk_level` (the `api` does). The only threshold use here: read Redis `iw:settings:thresholds` (no cache) when creating a finding and publish `finding.high_risk` if `score` is at or above the module threshold ([ADR 0305](../.docs/decisions/0305-threshold-storage.md)).
- Default thresholds are measured, not chosen: `eval/thresholds.json` is the source (best F1 of the rules-only gold run; M1 from the recorded DeepSeek run `eval/llm-run-deepseek-flash.json`, ADR 0318). A rule or gold-set change that moves them fails `tests/test_eval_thresholds.py`: run `python eval/run.py --write-thresholds` and copy the values into `events.DEFAULT_THRESHOLDS` and the API's `DEFAULTS` ([ADR 0316](../.docs/decisions/0316-default-thresholds-from-evaluation.md)).
- Every `iw:events` message is the envelope `{type, emitted_at (UTC ISO), data}` with `data` exactly `{id, module, score, title, url, platform}` (the schema's optional `risk_level` is never sent by analytics); the API relay silently drops anything else ([integration-plan §6](../.docs/integration-plan.md), `contracts/schemas/events.schema.json`).
- Logs are JSON on stdout, except the CLI (`python -m investwatch_analytics.cli`), which logs to stderr because its stdout is the findings JSON. A collector of CLI runs reads stderr.
- Scraped text is untrusted: put it in a delimited block, tell the model to ignore instructions inside it, limit its length.
- LLM: an OpenAI-compatible chat completions API configured by env only (`LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`, limits in `.env.example`). Hosted default DeepSeek Flash ([ADR 0318](../.docs/decisions/0318-hosted-llm-deepseek-flash.md); Gemma 4 on the Gemini API, [ADR 0317](../.docs/decisions/0317-hosted-llm-gemma-on-gemini-api.md), is the documented alternative); local Ollama `/v1` with `gemma3:4b` must keep working as the swap target, so no provider-specific SDK or features ([ADR 0304](../.docs/decisions/0304-llm-serving.md)).
- Embeddings: an OpenAI-compatible `/embeddings` endpoint, env only (`EMBED_*`), local only (`bge-m3` on `ollama`); never a paid hosted API ([ADR 0313](../.docs/decisions/0313-embeddings-model-and-serving.md)). Off or failing means `model.embedder = null`, never a failed document. The topic gate drops only `third_party`/`unknown` text with no investment signal and logs `off_topic`; a near-duplicate is analyzed, not dropped ([ADR 0314](../.docs/decisions/0314-topic-gate-and-near-duplicates.md)).
- The LLM only decides checks the rules defer: an `llm:` block in the catalogue plus the rule's `ask_llm`. Never send a deterministic rules-only verdict, and never let a verdict carry a quote that is not in the document ([ADR 0309](../.docs/decisions/0309-llm-prompt-and-cache-contract.md)). Tests never call a real LLM: `tests/llm_stub.py` and the conftest guard.

## Stack and done

Python, pytest. Done means a document from the stream yields schema-valid findings, an `iw:events` message, and the gold-set evaluation (`.docs/analytics-plan.md` §8) still runs.
