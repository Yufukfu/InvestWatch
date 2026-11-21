# analytics (module C)

Consumes the Redis Stream `iw:documents` (consumer group `analytics`), runs modules M1-M3, inserts `findings` and publishes to `iw:events`. The logic lives in the docs, not here:

- Pipeline, rules and LLM layer: [`.docs/analytics-plan.md`](../.docs/analytics-plan.md) §2 (pipeline), §4-6 (M1-M3), §7 (LLM), §8 (evaluation and calibration).
- Input contract `ScrapedDocument`: [`.docs/integration-plan.md`](../.docs/integration-plan.md) §3. Output `Finding`: §4. Events: §6.

## Rules that are easy to get wrong

- Rules before LLM. Anything checkable deterministically (regex, dictionaries, block metadata) runs without a model.
- Every LLM result needs an evidence quote that is verified as a substring of the document; otherwise the result is `uncertain`, not `fail`.
- Degrade, don't fail: if the LLM endpoint is down the pipeline runs rules-only and records `model.llm = null`.
- Store the raw `score` (0-1); the threshold is applied in `api`, never here.
- Scraped text is untrusted: put it in a delimited block, tell the model to ignore instructions inside it, limit its length.
- LLM: Gemma through an Ollama-compatible HTTP API, configured by env (`LLM_BASE_URL`, `LLM_MODEL`); no paid APIs.

## Stack and done

Python, pytest. Done means a document from the stream yields schema-valid findings, an `iw:events` message, and the gold-set evaluation (`.docs/analytics-plan.md` §8) still runs.
