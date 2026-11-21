// The headless Claude Code session. Flags are pinned against `claude --help` of 2.1.330
// (fixtures/claude-help.txt): there is no --max-turns, so a dollar budget and a wall-clock timeout bound it.
// Never --bare, --restricted or --safe-mode: they skip the project's hooks, and git-guard must run.
import { spawnSync } from 'node:child_process';
import { safeBranch } from './prompt.mjs';

export const TOOLS = ['Bash', 'Read', 'Edit', 'Write', 'Grep', 'Glob'];
export const TIMEOUT_MS = 20 * 60 * 1000;

// Rule semantics probed on 2.1.330 (see fixtures/README.md): a deny beats any allow, also a project one;
// `Read(./**)` confines reads (and Grep) to the clone; Write is governed by `Edit(...)` rules; `cmd 11 *`
// does not match `cmd 110`; a `*` inside a deny pattern matches (`gh * --repo *`); a leading VAR=x or a
// chained `&& other` stops an allow rule matching. Project allow rules of an untrusted directory (every
// fresh clone) are ignored in -p, so this list is the whole allow-list; project hooks still run.
export const DENY = [
  'Bash(gh pr review:*)', 'Bash(gh pr merge:*)', 'Bash(gh pr ready:*)', 'Bash(gh pr close:*)', 'Bash(gh pr create:*)', 'Bash(gh api:*)',
  'Bash(gh repo:*)', 'Bash(gh secret:*)', 'Bash(gh workflow:*)', 'Bash(gh auth:*)', 'Bash(gh alias:*)', 'Bash(gh extension:*)',
  'Bash(gh * --repo *)', 'Bash(gh * --repo=*)', 'Bash(gh * -R *)',
  'Bash(curl:*)', 'Bash(wget:*)', 'Bash(git push --force:*)', 'Bash(git remote:*)', 'Bash(git config:*)',
  'Edit(./.git/**)', 'Edit(./.claude/**)', 'Read(./.env)', 'Read(./**/.env)',
  // read-only git forms that write or read outside the clone (whole-branch review)
  'Bash(git * --output*)', 'Bash(git * --no-index*)', 'Bash(git blame * --contents*)',
  // a body only from the agent's own reply files: no file elsewhere, no inline body
  'Bash(gh * --body-file /*)', 'Bash(gh * --body-file ~*)', 'Bash(gh * --body-file ..*)', 'Bash(gh * -F *)', 'Bash(gh * --body *)', 'Bash(gh * -b *)',
  'WebFetch', 'WebSearch',
];

const READ = [
  'Read(./**)', 'Grep', 'Glob',
  'Bash(git status:*)', 'Bash(git diff:*)', 'Bash(git log:*)', 'Bash(git show:*)', 'Bash(git blame:*)',
  'Bash(gh pr view:*)', 'Bash(gh pr diff:*)', 'Bash(gh issue list:*)', 'Bash(gh issue view:*)',
  // Edit(./**) does not cover dot-directories (probe), so the reply folder is listed on its own
  'Edit(./.iw-watch/**)',
];
const SAFE_PATH = /^\/[A-Za-z0-9._/-]+$/;
// Tests run code. That is acceptable on my own branch, where the text that reached the agent came only from
// people with write access (scan.mjs TRUSTED); a review of someone else's branch never runs their code.
const FIX = [
  'Bash(git add:*)', 'Bash(git commit:*)',
  // a fresh clone has no node_modules: the lockfile only, and no install scripts
  'Bash(npm ci --ignore-scripts:*)',
  'Bash(node --test:*)', 'Bash(npm test:*)', 'Bash(npm run test:*)', 'Bash(npm run lint:*)', 'Bash(npm run typecheck:*)',
  'Bash(npx vitest run:*)', 'Bash(npx tsc:*)', 'Bash(npx oxlint:*)',
  // a package below the root without cd: npm --prefix web test
  // plain * only: a rule with an inner * and a trailing :* never matched (live run on PR #40)
  'Bash(npm --prefix * ci --ignore-scripts)', 'Bash(npm --prefix * test)', 'Bash(npm --prefix * test *)',
  'Bash(npm --prefix * run lint)', 'Bash(npm --prefix * run typecheck)',
  'Bash(git restore --staged:*)',
  'Bash(pytest:*)', 'Bash(python -m pytest:*)', 'Bash(uv run pytest:*)',
  'Bash(openspec validate:*)', 'Bash(node .claude/skills/iw-docs-update/scripts/docs-check.mjs:*)',
];

/** Least privilege per session: push only this branch, comment only on this PR, nothing outward in a dry run */
export function allowList({ kind, pr, headRef, dryRun, cwd }) {
  if (!Number.isInteger(pr)) throw new Error('allowList needs a PR number');
  const fixes = kind === 'address-review' || kind === 'ci-failed';
  if (fixes && !safeBranch(headRef)) throw new Error(`refusing unsafe branch name ${JSON.stringify(headRef)}`);
  if (cwd !== undefined && !SAFE_PATH.test(cwd)) throw new Error(`refusing clone path ${JSON.stringify(cwd)}`);
  // a review edits nothing but its own reply; a fix edits the clone, never .git/ or .claude/ (see DENY)
  const allow = [...READ, ...(fixes ? ['Edit(./**)', ...FIX] : [])];
  // agents write `cd <clone> && git status`, and every part of a chain must be allowed (live run, PR #39)
  if (cwd) allow.push(`Bash(cd ${cwd})`, `Bash(cd ${cwd}/*)`);
  if (!dryRun) {
    if (fixes) allow.push(`Bash(git push origin ${headRef})`, `Bash(git push -u origin ${headRef})`);
    allow.push(
      `Bash(gh pr comment ${pr} --body-file .iw-watch/reply.md)`,
      'Bash(gh issue create --title * --assignee * --body-file .iw-watch/issue.md)',
      'Bash(gh issue create --title * --body-file .iw-watch/issue.md)',
    );
  }
  return allow;
}

/** Explicit denies on top: they hold even if some other settings source allowed the command */
export function denyList({ kind, dryRun }) {
  const fixes = kind === 'address-review' || kind === 'ci-failed';
  const deny = [...DENY];
  if (!fixes) deny.push('Bash(git push:*)', 'Bash(git commit:*)', 'Bash(git add:*)');
  if (dryRun) deny.push('Bash(git push:*)', 'Bash(gh pr comment:*)', 'Bash(gh issue create:*)', 'Bash(gh issue comment:*)');
  return [...new Set(deny)];
}

export function claudeArgs({ kind, pr, headRef, dryRun, budgetUsd = 2, model, cwd }) {
  return [
    '-p',
    '--permission-mode', 'dontAsk',
    '--permission-prompts', 'none',
    '--no-session-persistence',
    '--output-format', 'stream-json', '--verbose',
    '--max-budget-usd', String(budgetUsd),
    ...(model ? ['--model', model] : []),
    '--tools', ...TOOLS,
    '--allowedTools', ...allowList({ kind, pr, headRef, dryRun, cwd }),
    '--disallowedTools', ...denyList({ kind, dryRun }),
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
  // no IW_* escape flags, and no iw-watch secrets (webhook URL, notify command): fix sessions run tests, which can read the env
  for (const [k, v] of Object.entries(env)) if (!/^iw_/i.test(k) && !/^iwatch_/i.test(k)) out[k] = v;
  out.IWATCH_SESSION = '1';
  return out;
}

export function runSession({ spawn = spawnSync, cwd, prompt, args, env, timeoutMs = TIMEOUT_MS }) {
  const r = spawn('claude', args, { cwd, input: prompt, encoding: 'utf8', timeout: timeoutMs, maxBuffer: 256 * 1024 * 1024, env: childEnv(env), stdio: ['pipe', 'pipe', 'pipe'] });
  const timedOut = r.error?.code === 'ETIMEDOUT' || r.signal === 'SIGTERM';
  const parsed = parseStream(r.stdout);
  return { ...parsed, code: r.status, timedOut, stderr: String(r.stderr || '').slice(-2000), ok: !timedOut && r.status === 0 && !parsed.isError };
}
