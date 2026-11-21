# Documentation index

Agents: start at `CLAUDE.md`, then this map. Docs are in English; user-facing dashboard texts are Polish.

| File | What it is | Owner |
|---|---|---|
| `STATUS.md` | Current milestone, per-module state, blockers. Update on every milestone move. | all |
| `integration-plan.md` | Architecture, contracts v1, REST, events, milestones | C |
| `analytics-plan.md` | Analytics module plan | C |
| `ai-workflow.md` | AI process (tools, context, controls) and the append-only AI work log table, the jury evidence | all |
| `decisions/` | ADRs: why we chose X. Human-authored. | all |
| `../openspec/specs/` | What the system does now | owner of module |
| `../openspec/changes/` | Changes in flight | author |
| `../.claude/SDLC.md`, `CODE_REVIEW.md` | Process and review bar | all |
| UKNF materials (`*.pdf`, `*.docx`) | Challenge description, rules R1-R18 | read-only |

Rule: don't duplicate. Link to the owning file. A doc claim that matters gets checked against the code before it is relied on.
