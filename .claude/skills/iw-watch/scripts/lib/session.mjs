// The headless Claude Code session. Flags are pinned against `claude --help` of 2.1.330
// (fixtures/claude-help.txt): there is no --max-turns, so a dollar budget and a wall-clock timeout bound it.
// Never --bare, --restricted or --safe-mode: they skip the project's hooks, and git-guard must run.
import { spawnSync } from 'node:child_process';
import { safeBranch } from './prompt.mjs';

export const TOOLS = ['Bash', 'Read', 'Edit', 'Write', 'Grep', 'Glob'];
export const TIMEOUT_MS = 20 * 60 * 1000;

export const DENY = [
  'Bash(gh pr review:*)', 'Bash(gh pr merge:*)', 'Bash(gh pr ready:*)', 'Bash(gh pr close:*)', 'Bash(gh api:*)',
  'Bash(gh repo:*)', 'Bash(gh secret:*)', 'Bash(gh workflow:*)', 'Bash(gh auth:*)', 'Bash(gh alias:*)',
  'Bash(curl:*)', 'Bash(wget:*)', 'Bash(git push --force:*)', 'Bash(git remote:*)', 'Bash(git config:*)',
  'WebFetch', 'WebSearch',
];

const READ = [
  'Read', 'Grep', 'Glob', 'Write', 'Edit',
  'Bash(git status:*)', 'Bash(git diff:*)', 'Bash(git log:*)', 'Bash(git show:*)', 'Bash(git blame:*)',
  'Bash(ls:*)', 'Bash(gh pr view:*)', 'Bash(gh pr diff:*)', 'Bash(gh issue list:*)', 'Bash(gh issue view:*)',
];
// Tests run code. That is acceptable on my own branch, where the text that reached the agent came only from
// people with write access (scan.mjs TRUSTED); a review of someone else's branch never runs their code.
const FIX = [
  'Bash(git add:*)', 'Bash(git commit:*)',
  'Bash(node --test:*)', 'Bash(npm test:*)', 'Bash(npm run test:*)', 'Bash(npm run lint:*)', 'Bash(npm run typecheck:*)',
  'Bash(pytest:*)', 'Bash(python -m pytest:*)', 'Bash(uv run pytest:*)',
  'Bash(openspec validate:*)', 'Bash(node .claude/skills/iw-docs-update/scripts/docs-check.mjs:*)',
];

/** Least privilege per session: push only this branch, comment only on this PR, nothing outward in a dry run */
export function allowList({ kind, pr, headRef, dryRun }) {
  if (!Number.isInteger(pr)) throw new Error('allowList needs a PR number');
  const fixes = kind === 'address-review' || kind === 'ci-failed';
  if (fixes && !safeBranch(headRef)) throw new Error(`refusing unsafe branch name ${JSON.stringify(headRef)}`);
  const allow = [...READ, ...(fixes ? FIX : [])];
  if (!dryRun) {
    if (fixes) allow.push(`Bash(git push origin ${headRef})`, `Bash(git push -u origin ${headRef})`);
    allow.push(`Bash(gh pr comment ${pr}:*)`, 'Bash(gh issue create:*)', 'Bash(gh issue comment:*)');
  }
  return allow;
}

export function claudeArgs({ kind, pr, headRef, dryRun, budgetUsd = 2, model }) {
  return [
    '-p',
    '--permission-mode', 'dontAsk',
    '--permission-prompts', 'none',
    '--no-session-persistence',
    '--output-format', 'stream-json', '--verbose',
    '--max-budget-usd', String(budgetUsd),
    ...(model ? ['--model', model] : []),
    '--tools', ...TOOLS,
    '--allowedTools', ...allowList({ kind, pr, headRef, dryRun }),
    '--disallowedTools', ...DENY,
  ];
}

export function parseStream(text) {
  let result = null;
  for (const line of String(text || '').split('\n')) {
    if (!line.trim().startsWith('{')) continue;
    try {
      const j = JSON.parse(line);
      if (j.type === 'result') result = j;
    } catch { /* a partial or foreign line */ }
  }
  if (!result) return { result: null, isError: true, denials: [], cost: 0, summary: 'the session ended without a result' };
  return {
    result,
    isError: Boolean(result.is_error),
    denials: result.permission_denials || [],
    cost: result.total_cost_usd || 0,
    turns: result.num_turns,
    subtype: result.subtype,
    summary: String(result.result || '').slice(0, 2000),
  };
}

export const pushDenied = (denials) => denials.some((d) => /(^|[\s;&|(])git\s+push\b/.test(d.tool_input?.command || ''));

/** The session's environment: no IW_* escape flags reach it, whatever the caller's shell had */
export function childEnv(env) {
  const out = {};
  for (const [k, v] of Object.entries(env)) if (!/^iw_/i.test(k)) out[k] = v;
  out.IWATCH_SESSION = '1';
  return out;
}

export function runSession({ spawn = spawnSync, cwd, prompt, args, env, timeoutMs = TIMEOUT_MS }) {
  const r = spawn('claude', args, { cwd, input: prompt, encoding: 'utf8', timeout: timeoutMs, maxBuffer: 256 * 1024 * 1024, env: childEnv(env), stdio: ['pipe', 'pipe', 'pipe'] });
  const timedOut = r.error?.code === 'ETIMEDOUT' || r.signal === 'SIGTERM';
  const parsed = parseStream(r.stdout);
  return { ...parsed, code: r.status, timedOut, stderr: String(r.stderr || '').slice(-2000), ok: !timedOut && r.status === 0 && !parsed.isError };
}
