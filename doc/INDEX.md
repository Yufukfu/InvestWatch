# Documentation index

Agents: start at `CLAUDE.md`, then this map. Language is English; older files marked (PL) are Polish and being translated.

| File | What it is | Owner |
|---|---|---|
| `STATUS.md` | Current milestone, per-module state, blockers. Update on every milestone move. | all |
| `plan-integracji.md` (PL) | Architecture, contracts v1, REST, events, milestones | C |
| `plan-analityka.md` (PL) | Analytics module plan | C |
| `ai-workflow.md` | How we use AI assistants (jury criterion) | all |
| `ai-log.md` | Append-only evidence log for the above | all |
| `decisions/` | ADRs: why we chose X. Human-authored. | all |
| `../openspec/specs/` | What the system does now | owner of module |
| `../openspec/changes/` | Changes in flight | author |
| `../.claude/SDLC.md`, `CODE_REVIEW.md` | Process and review bar | all |
| UKNF materials (`*.pdf`, `*.docx`) | Challenge description, rules R1-R18 | read-only |

Rule: don't duplicate. Link to the owning file. A doc claim that matters gets checked against the code before it is relied on.
