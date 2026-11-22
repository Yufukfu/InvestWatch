## 1. Analytics reads the stored content hash

- [x] 1.1 Tests: a loaded document keeps its stored `content_hash` for compatibility-character text and stays without one when absent; `Preprocessed` has no `content_hash` and the module exports no `content_hash()`; NFKC `normalize()` still folds `ﬁ` and full-width digits for matching
- [x] 1.2 Remove `content_hash()` and `Preprocessed.content_hash` from `preprocessing.py`; update the module docstring and `test_preprocessing.py`
- [x] 1.3 Mutation check: mutations: 5 tried, 5 caught (re-add `content_hash()`, re-add `Preprocessed.content_hash`, NFKC to NFC in `normalize`, loader recomputes the hash from NFKC text, loader drops the stored hash). Red first: `test_preprocessing_computes_no_content_hash` failed on the old code; the storage tests are green on old code too because the loader already passed the value through, the loader mutants are their red proof

## 2. LLM cache keyed by the stored hash

- [x] 2.1 Tests: the judge gets the document's stored `content_hash` unchanged (also for compatibility characters) and None without one; a document without a stored hash bypasses the cache; two stored hashes for the same text give two entries; the LLM test helpers pass the stored value
- [x] 2.2 `rules/engine.py` passes `ctx.doc.content_hash`; `HttpJudge.judge` takes `str | None` and skips the cache without one
- [x] 2.3 Mutation check: mutations: 5 tried, 5 caught (engine passes None, engine hashes its NFKC text, judge never bypasses the cache, bypass inverted, cache key on a constant). Red first: `test_no_stored_hash_bypasses_the_cache` failed with `TypeError` (None joined into the key) and the engine tests with `AttributeError` on the removed `pre.content_hash`

## 3. Docs

- [x] 3.1 `.docs/analytics-plan.md` §2 row 1 and the §7 cache line, ADR 0309's cache-key line, `analytics/.../llm/cache.py` docstring, `.docs/status/platform.md`

## 4. Closing

- [x] 4.1 Apply iw-docs-update and add the iw-ai-log row (docs-check ok)
- [x] 4.2 Run iw-pr-review and fix real findings (iw-reviewer, security folded in, on ade784f5..471c5ac0: no blocking findings; test-diff-check: no weakened tests)
