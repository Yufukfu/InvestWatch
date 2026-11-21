# AI-Assisted Development Log

This log documents how the team builds InvestWatch with AI assistants (evaluation criterion: "standardized software development process with AI assistants", 20%). Add a short entry at every milestone and whenever the process changes.

## Process

- **Spec-driven development with OpenSpec:** every change starts as a spec/proposal; implementation follows an approved spec.
- **Single source of truth:** the contracts in `contracts/` (JSON Schema) and the plans in `.docs/` are the context for both people and AI assistants.
- **Tools:** Claude Code (planning, code generation, review), OpenSpec (specs and change proposals).
- **Review rules for generated code:** every AI-generated change is read by a human before merge; no secrets in prompts or commits; dependencies added by AI are checked with `npm audit` / `pip-audit`.
- **Language:** technical documentation, code and commit messages in English; user-facing texts in Polish.

## Log

| When | Who | What was done with AI | Outcome / lesson |
|---|---|---|---|
| Sat 11:15 | C | Read all 16 HackNation tasks and compared the top candidates (scope, criteria, constraints) | Team picked #InvestWatch |
| Sat 13:00 | C | Summarized the UKNF task, rules and annexes (18 risk-information rules, registry links, advisory definition) | Requirements in one place |
| Sat 13:40 | C | Drafted the integration plan (contracts, REST/WS API, milestones) and the analytics work plan | `.docs/integration-plan.md`, `.docs/analytics-plan.md` |
| Sat 14:10 | C | Applied team sync decisions; translated technical docs to English; started this log | English docs; OpenSpec adopted |
| Sat 14:05 | B | Generated a full service skeleton with Claude Code, then reviewed it against the team plan | The AI had filled open decisions (contracts, scraper design) with guesses from draft docs. Kept only the agreed repository structure; open decisions are left for ADRs |
