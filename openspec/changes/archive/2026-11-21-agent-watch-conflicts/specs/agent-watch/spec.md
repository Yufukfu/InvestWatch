## ADDED Requirements

### Requirement: Merge conflicts on my PRs are handled

The watcher SHALL raise a `conflict` item for my PR when GitHub reports it `CONFLICTING`, once per head sha. In headless mode the runner SHALL merge the base into the PR branch and commit the merge itself. It SHALL commit only when no unmerged path and no conflict marker remains, and SHALL push without force. A conflict in `.claude/`, `CLAUDE.md`, `.github/`, `.mcp.json` or `.npmrc` SHALL go to the human with no session.

#### Scenario: Agent resolves a conflict

- **WHEN** my PR conflicts with main in `web/a.ts` and the agent resolves and stages it
- **THEN** the runner commits a merge commit, pushes the branch and posts the reply

#### Scenario: Clean merge needs no agent

- **WHEN** git merges the base with no conflict in the clone
- **THEN** the runner commits, pushes and posts a short reply without starting a session

#### Scenario: Markers left

- **WHEN** a conflict marker or an unmerged path remains after the session
- **THEN** nothing is committed or pushed and the human is told which file
