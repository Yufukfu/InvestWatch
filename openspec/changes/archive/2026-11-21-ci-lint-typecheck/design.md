# Design

`--if-present` keeps the loop generic for any Node service without those scripts. Order: lint, typecheck, test, so cheap failures come first. Audit stays first. Verified locally by running the three scripts in `web/` (the same commands CI will run after `npm ci`).
