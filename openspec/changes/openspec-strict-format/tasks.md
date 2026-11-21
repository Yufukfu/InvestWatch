# Tasks

## 1. Specs

- [x] 1.1 Read the exact error per spec with the CI-pinned `npx -y @fission-ai/openspec@2.1.1 validate --all --strict --no-interactive` on `origin/main` (5 failing specs, 15 requirements over 500 characters); confirm from the 2.1.1 source (`requirement-text.js`) that every body line before the first `####` counts.
- [x] 1.2 MODIFIED delta per requirement: move the overflow sentences into that requirement's scenarios without changing what they say; keep headers and existing scenario names. mutations: n/a, specs only (no guard, parser or rule code).
- [x] 1.3 Check that every removed clause reappears in the same requirement (word diff), and that the archived specs equal the edited specs byte for byte.

## 2. Closing

- [x] 2.1 `iw-docs-update` (`.docs/status/platform.md`), AI log row, `docs-check` clean.
- [x] 2.2 `openspec validate --all --strict` clean on 2.1.1, before and after archive.
