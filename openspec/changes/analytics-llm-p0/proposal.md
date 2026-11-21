# Proposal

## Why

Stage 2 (etap 2) of analytics. After stage 1, M2 checks only R1-R3 with regexes and every finding says `model.llm = null`. The plan's 17:00-20:00 window (`.docs/analytics-plan.md` §9) is the rest of the P0 rules plus the LLM for R3, R17 and R18, so that Integration #2 shows M2 end to end. Without an LLM layer, R17 ("implying supervisory approval") cannot be judged at all, and R3 stays coarse on its known borderline cases (skeleton follow-ups 14 and 19). The sibling stage-2 change `analytics-m1-m3` also needs an LLM hook for its semantic signals S1.4, S1.5, S3.3 and S3.4. This change provides that hook, so the M1/M3 rule code does not change when the LLM lands.

**Depends on `analytics-worker` landing first.** That change (branch `analytics/analytics-worker`, not merged yet) adds `worker.py`, `config.py` worker settings, `AdvertiserRef` on `Finding` and `analytics/compose.yaml`, all of which this change edits. Apply starts from a `main` that contains `analytics-worker`. Task groups 1-4 touch only rule code and can start before it lands. Infra PR #18 (`infra-compose`) provides the optional `ollama` service (profile `llm`) and the `egress` network.

## What Changes

- **LLM layer** (`.docs/analytics-plan.md` §7, ADR 0304):
  - A chat completions client for any OpenAI-compatible endpoint, configured by env only (`LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`, plus timeouts and limits). It uses no provider SDK, only `httpx`. With `LLM_BASE_URL` unset the LLM is disabled and analytics runs rules-only. Local Ollama `/v1` with `gemma3:4b` works with the same code and is a fully supported, tested path. Whether it becomes the demo default (the task text asks for free, on-premise models only; ADR 0304 has a hosted default under a mentor exception) is pending Damian's decision and not part of this change.
  - One call per document, module and chunk, with `response_format: {"type": "json_object"}` and `temperature: 0`. It asks only about the checks the rules deferred to the LLM. When nothing is deferred, no call is made.
  - Scraped text goes into one `<document>…</document>` block. The system prompt says to ignore instructions inside it. Tag look-alikes in the text are neutralized. The text is split on sentence boundaries into chunks of about 3k tokens, and the worst chunk result wins.
  - Pydantic validation of the response. Every `evidence_quote` must be a verbatim substring of the chunk that was sent and at least 8 characters long, otherwise the result is `uncertain`. Rule ids that were not asked about are dropped.
  - A Redis response cache keyed by `(content_hash, prompt_version, model)`, plus module, chunk and the requested checks. Here `prompt_version` is a hash of the rendered system prompt.
  - Degradation: when the endpoint is down, times out, returns HTTP errors or malformed output, or the per-document budget runs out, the rules-only results are kept. A circuit breaker skips the LLM for a cooldown after repeated failures. `model.llm` names the model only when at least one rule result actually used it, and is `null` otherwise.
- **Seam for M1/M3:** any catalogue entry, in any module, can declare an `llm:` block (question, when to ask). The engine collects the deferred checks, makes one judge call per module and merges the verdicts into the rule results (`method: llm` or `hybrid`). `analytics-m1-m3` adds `llm:` blocks to its YAML and passes the judge through. It edits no rule classes.
- **M2 P0 rules** (plan §5), with their meaning taken from the challenge criteria document (`doc/ZASÓB … kryteria oceny informacji o ryzyku.docx`, cited as ZASÓB), each catalogue entry flipping to `implemented: true`:
  - R4: risk font size from `blocks`, against the dominant font size of the material.
  - R6: risk hidden in the footer, legal region or a footnote and not in the viewport on load.
  - R10: language consistency against the headline and body language (legal and footer blocks excluded), which needs a language guess per sentence.
  - R14: a clear past-performance disclaimer present in the material, with no proximity requirement.
  - R17: implying supervisory approval. Regex detection, and the LLM judges a supervisor mention that the regexes do not settle.
  - R18: supervision as a safety argument. Regex for the same sentence, and the LLM judges cross-sentence cases.
  - R3: the LLM decides only R3's borderline proximity cases (a warning just outside the window), never an absent warning.
  - R4, R6 and R10 are `not_applicable` with `brak informacji o ryzyku` when the material has no risk information, so R3 alone counts it.
  - The visual rules R4 and R6 return `not_applicable` without `blocks`, never `pass`. Visual results carry `evidence_locator` (`viewport`, `bbox`), a field that is already optional in contract v1.
- **Wiring:** `analyze(…, judge=None)` stays pure: the judge is injected. The worker builds the judge from env. The CLI uses it when `LLM_BASE_URL` is set and has `--no-llm`. `analytics/compose.yaml` passes the `LLM_*` env and joins the `egress` network for a hosted provider.
- **Out of scope:**
  - The P1/P2 rules (R5, R7, R8, R9, R11-R13, R15, R16).
  - M1/M3 signals and their prompts. Those belong to `analytics-m1-m3`, and this change only defines the interface.
  - Embeddings, the topic gate, near-dup detection, LLM-written summaries, OCR.
  - The gold set and `eval/run.py`.
  - The infra `ollama` service itself (PR #18).
  - Any live LLM call in tests: tests use a local stub HTTP server.
- **Owner:** Damian (`analytics/`).
- **Contracts:** the change touches no contract, REST route or event. It fills fields that already exist in `Finding` v1: `rules[].method` (`llm`, `hybrid`), `rules[].evidence_locator` and `model.llm`. It needs no version bump.

## Capabilities

### New Capabilities
- `llm-analysis`: the OpenAI-compatible LLM judge. Covers config, prompt and delimiting, chunking, validation, quote verification, cache, budget, circuit breaker, degradation, and the catalogue `llm:` seam used by M1-M3.

### Modified Capabilities
- `m2-compliance-rules`: the catalogue gains `llm:` blocks and more implemented rules. Evidence may come from the LLM (`method: llm` or `hybrid`). R3 adds LLM refinement of borderline cases. New requirements cover R4, R6, R10, R14, R17 and R18.
- `document-analysis`: preprocessing adds a language guess per sentence. M2 finding assembly reports `model.llm` and the Polish summary according to whether the LLM was used.

## Impact

- **Code, under `analytics/` only:**
  - New: `llm/` (`client.py`, `prompt.py`, `chunking.py`, `judge.py`, `cache.py`).
  - Changed: `rules/engine.py`, `rules/m2.py`, `rules/m2_rules.yaml`, `preprocessing.py`, `models.py` (`evidence_locator`), `modules/m2.py`, `pipeline.py`, `config.py`, `cli.py`, `worker.py`, `compose.yaml`, `.env.example`, `README.md`, `tests/`.
- **Dependencies:** `httpx` (runtime, pinned, `pip-audit` before merge). The stub server uses the stdlib `http.server`, so there is no new dev dependency.
- **ADRs:**
  - 0309, the LLM prompt, response and cache contract, and what the LLM may decide.
  - 0310, chunking and the per-document LLM budget.
- **Docs:**
  - `.docs/analytics-plan.md` §7: the response is an object wrapper, and `prompt_version` is a hash.
  - `analytics/CLAUDE.md` (LLM env), `analytics/README.md`.
  - The STATUS row is updated by the coordinator, not this change.
- **Security:** the prompts are built from scraped text, so this change gets a `focus: security` review (iw-reviewer). The injection and quote-verification scenarios are part of the review scope.
- **Infra note for Kacper:** Ollama's default context window may be smaller than a chunk plus the prompt, and `/v1` cannot set `num_ctx` per request. Set `OLLAMA_CONTEXT_LENGTH` in the `ollama` service (ADR 0310, to verify on the smoke run).
