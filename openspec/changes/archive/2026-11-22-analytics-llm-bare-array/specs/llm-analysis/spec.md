## MODIFIED Requirements

### Requirement: Validated response with verified quotes
The response content SHALL be a JSON object `{"results": [{"rule_id", "result", "evidence_quote", "explanation"}]}`, or a bare JSON array of those items, which SHALL be read as `{"results": <array>}` (hosted Gemma 4 `gemma-4-26b-a4b-it` answers so in JSON mode). It SHALL be validated per item with Pydantic; an invalid item SHALL be dropped and its check keeps the rules-only result. An `evidence_quote` SHALL be accepted only when it is at least 8 characters long and occurs in the chunk sent; otherwise the verdict SHALL become `uncertain` with `evidence: null`. Accepted evidence SHALL be a verbatim substring of the document `text`.

#### Scenario: Hallucinated quote
- **WHEN** the stub answers R17 `fail` with `evidence_quote` `Produkt zatwierdzony przez KNF`, which is not in the document
- **THEN** R17 is `uncertain` with `evidence: null` and an explanation that the quote was not confirmed
- **AND** the explanation SHALL be in Polish

#### Scenario: Trivial quote
- **WHEN** the stub answers R17 `fail` with `evidence_quote` `KNF`
- **THEN** R17 is `uncertain`, because the quote is shorter than 8 characters

#### Scenario: Valid verdict
- **WHEN** the stub answers R17 `fail` with a quote that occurs in the document
- **THEN** R17 is `fail`, `evidence` is that exact substring, and `method` is `hybrid`
- **AND** a quote that differs only in whitespace SHALL be mapped back to the exact original span

#### Scenario: Result outside the allowed set
- **WHEN** the stub answers `{"rule_id": "R17", "result": "maybe", …}`
- **THEN** that item is dropped and R17 keeps its rules-only result
- **AND** an item SHALL also be invalid when `explanation` is not a string of at most 500 characters or `evidence_quote` is neither null nor a string of at most 400 characters

#### Scenario: Pass without quote
- **WHEN** the stub answers R18 `pass` with `evidence_quote: null` for a deferred R18
- **THEN** R18 is `pass` with `evidence: null` and `method: hybrid`
- **AND** a `fail` or `uncertain` verdict without an accepted quote, or any verdict whose given quote is not accepted, SHALL become `uncertain`

#### Scenario: Bare results array
- **WHEN** the stub answers HTTP 200 with content `[{"rule_id": "R17", "result": "fail", "evidence_quote": "<a sentence of the document>", "explanation": "x"}]`, optionally after a `<thought>` block or in a code fence
- **THEN** it is read as `{"results": [...]}`: R17 is `fail` with that quote, the same per-item validation and quote verification apply, and the response is cached like an object answer
- **AND** an empty array SHALL be a valid answer with no verdicts, and an item in the array that fails validation SHALL be dropped as in an object answer

### Requirement: Degrade to rules-only on any LLM failure
No LLM failure SHALL fail the document: the affected module's checks SHALL keep their rules-only results, the finding SHALL be produced and saved as usual, and a log line SHALL name the reason (`llm_unavailable`, `llm_timeout`, `llm_malformed`, `llm_budget_exhausted`) without document text. When any chunk of a module's call fails, all of that module's verdicts SHALL be dropped.

#### Scenario: LLM down
- **WHEN** `LLM_BASE_URL` points to a closed port and `m2-alfa-landing` is analyzed
- **THEN** the M2 finding is produced with the rules-only results, `model.llm = null`, and the log reason `llm_unavailable`
- **AND** a failure SHALL be a connection error, a timeout after `LLM_TIMEOUT_S`, HTTP 429, 401, 403 or 5xx, a body that is not chat-completions JSON, content that is neither a JSON object nor a JSON array (a string, number, boolean or null), an object without a `results` list, or an exhausted `LLM_DOC_BUDGET_S`

#### Scenario: Timeout
- **WHEN** the stub sleeps longer than `LLM_TIMEOUT_S` before answering
- **THEN** the call is abandoned within the timeout plus one second and the finding has the rules-only results with the log reason `llm_timeout`
- **AND** `LLM_TIMEOUT_S` SHALL also bound a server that trickles the response body, and a response over 1 MB SHALL be malformed

#### Scenario: Malformed JSON
- **WHEN** the stub answers HTTP 200 with content `{"results": [{"rule_id": "R17", "result": "fail"` (truncated)
- **THEN** the finding has the rules-only results, `model.llm = null`, and the log reason `llm_malformed`

#### Scenario: Wrong top-level shape
- **WHEN** the stub answers content `"R17 fail"`, `5`, `true` or `null` (valid JSON that is neither an object nor an array), or an object without a `results` list
- **THEN** it is treated as malformed and the rules-only results stay

#### Scenario: Server error
- **WHEN** the stub answers HTTP 500
- **THEN** the finding has the rules-only results and the log reason `llm_unavailable`

#### Scenario: One chunk fails
- **WHEN** a two-chunk document gets a valid answer for chunk 1 and HTTP 500 for chunk 2
- **THEN** none of the module's LLM verdicts are used
