// The headless Claude Code session. Flags are pinned against `claude --help` of 2.1.330
// (fixtures/claude-help.txt): there is no --max-turns, so a dollar budget and a wall-clock timeout bound it.
// Never --bare, --restricted or --safe-mode: they skip the project's hooks, and git-guard must run. The hooks
// that load are the base branch's: the runner refuses a branch that changes .claude/ (worktree.mjs).
//
// The session publishes nothing. It has no gh, no git push and no network: the runner pushes and posts after
// it (watch.mjs publish). Allow rules do not bound what a test runner does (Claude Code docs), so every Bash
// command runs in the Claude Code sandbox: no network, no writes outside the clone, no reads of the secrets
// listed in denyRead. Probed in -p on 2.1.330 (fixtures/README.md).
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { safeBranch } from './prompt.mjs';

export const TOOLS = ['Bash', 'Read', 'Edit', 'Write', 'Grep', 'Glob'];
export const TIMEOUT_MS = 20 * 60 * 1000;

const OUT_OF_CLONE = ['/*', '~*', '..*'];
const READERS = ['diff', 'show', 'log', 'blame', 'grep', 'cat-file', 'archive', 'format-patch'];

// Rule semantics probed on 2.1.330: a deny beats any allow; `Read(./**)` confines reads (and Grep) to the
// clone; Write is governed by `Edit(...)`; a chained `&& other` or a leading VAR=x stops an allow matching.
export const DENY = [
  'Bash(gh:*)', 'Bash(curl:*)', 'Bash(wget:*)', 'Bash(ssh:*)', 'Bash(scp:*)', 'Bash(nc:*)',
  'Bash(git push:*)', 'Bash(git remote:*)', 'Bash(git config:*)', 'Bash(git fetch:*)', 'Bash(git pull:*)',
  'Bash(git clone:*)', 'Bash(git submodule:*)', 'Bash(git -c:*)', 'Bash(git -C:*)', 'Bash(git credential:*)',
  'Bash(git * --output*)', 'Bash(git * --no-index*)', 'Bash(git blame * --contents*)', 'Bash(git * --exec*)',
  // `git diff /abs/file /dev/null` reads a file outside the repo even without --no-index (Adam, PR #48)
  ...READERS.flatMap((c) => OUT_OF_CLONE.flatMap((p) => [`Bash(git ${c} ${p})`, `Bash(git ${c} * ${p})`])),
  'Bash(npm install:*)', 'Bash(npm i:*)', 'Bash(npm ci:*)', 'Bash(npx -y:*)', 'Bash(npm exec:*)',
  'Edit(./.git/**)', 'Edit(./.claude/**)', 'Edit(./.github/**)', 'Edit(./**/CLAUDE.md)', 'Edit(./CLAUDE.md)', 'Edit(./.mcp.json)',
  'Read(./.git/**)', 'Read(./.env)', 'Read(./**/.env)',
  'WebFetch', 'WebSearch',
];

const FIX = [
  'Edit(./**)',
  'Bash(git status:*)', 'Bash(git diff:*)', 'Bash(git log:*)', 'Bash(git show:*)', 'Bash(git blame:*)',
  'Bash(git add:*)', 'Bash(git commit:*)', 'Bash(git restore --staged:*)',
  // test runners run code: allowed because of the sandbox, not because of these rules
  'Bash(node --test:*)', 'Bash(npm test:*)', 'Bash(npm run test:*)', 'Bash(npm run lint:*)', 'Bash(npm run typecheck:*)',
  'Bash(npx vitest run:*)', 'Bash(npx tsc:*)', 'Bash(npx oxlint:*)',
  // plain * only: a rule with an inner * and a trailing :* never matched (live run on PR #40)
  'Bash(npm --prefix * test)', 'Bash(npm --prefix * test *)', 'Bash(npm --prefix * run lint)', 'Bash(npm --prefix * run typecheck)',
  'Bash(pytest:*)', 'Bash(python -m pytest:*)', 'Bash(uv run pytest:*)',
  'Bash(openspec validate:*)', 'Bash(node .claude/skills/iw-docs-update/scripts/docs-check.mjs:*)',
];

const fixes = (kind) => ['address-review', 'ci-failed', 'conflict'].includes(kind);

/** Least privilege per session. A review reads the PR range only, by its exact forms. */
export function allowList({ kind, pr, baseRef }) {
  if (!Number.isInteger(pr)) throw new Error('allowList needs a PR number');
  const allow = ['Read(./**)', 'Grep', 'Glob', 'Edit(./.iw-watch/**)', 'Bash(git status)'];
  if (fixes(kind)) return [...allow, ...FIX];
  if (!safeBranch(baseRef)) throw new Error(`refusing unsafe branch name ${JSON.stringify(baseRef)}`);
  const range = `origin/${baseRef}...refs/iw/pr-${pr}`;
  const log = `origin/${baseRef}..refs/iw/pr-${pr}`;
  return [
    ...allow,
    `Bash(git diff ${range})`, `Bash(git diff --stat ${range})`, `Bash(git diff --name-only ${range})`, `Bash(git diff ${range} -- *)`,
    `Bash(git log ${log})`, `Bash(git log --oneline ${log})`, `Bash(git log --stat ${log})`,
    `Bash(git show refs/iw/pr-${pr}:*)`,
  ];
}

export function denyList({ kind, denyRead = [] }) {
  // the same paths for the Read tool, which the sandbox does not cover (absolute rules start with //)
  const deny = [...DENY, ...denyRead.filter((p) => p.startsWith('/')).flatMap((p) => [`Read(/${p})`, `Read(/${p}/**)`])];
  if (!fixes(kind)) deny.push('Bash(git commit:*)', 'Bash(git add:*)', 'Edit(./**)');
  return [...new Set(deny)];
}

/** Secrets a sandboxed command must not read, plus the .env files the runner found (watch.mjs) */
export function denyReadPaths({ home, stateDir, envFiles = [], configDir }) {
  const h = (p) => path.join(home, p);
  return [
    h('.ssh'), h('.config/gh'), h('.aws'), h('.gnupg'), h('.netrc'), h('.npmrc'), h('.docker'), h('.kube'),
    h('.zshenv'), h('.zshrc'), h('.zprofile'), h('.bashrc'), h('.bash_profile'), h('.profile'), h('.git-credentials'),
    h('.claude'), h('.claude.json'), h('.config'), h('.azure'), h('.gcloud'), h('Library/Keychains'), h('Library/Application Support/gh'),
    ...(configDir ? [configDir] : []), ...(stateDir ? [stateDir] : []), ...envFiles,
  ];
}

export function sandboxSettings({ denyRead = [] } = {}) {
  return {
    sandbox: {
      enabled: true,
      failIfUnavailable: true,
      allowUnsandboxedCommands: false,
      autoAllowBashIfSandboxed: false,
      network: { allowedDomains: [] },
      filesystem: { denyRead },
    },
  };
}

export function claudeArgs({ kind, pr, baseRef, budgetUsd = 2, model, denyRead = [] }) {
  return [
    '-p',
    '--permission-mode', 'dontAsk',
    '--permission-prompts', 'none',
    '--no-session-persistence',
    // no user-level allow rules, plugins or hooks, and no MCP servers: only the base branch's project settings
    '--setting-sources', 'project',
    '--strict-mcp-config',
    // CLI settings outrank project settings, so the branch cannot switch the sandbox off
    '--settings', JSON.stringify(sandboxSettings({ denyRead })),
    '--output-format', 'stream-json', '--verbose',
    '--max-budget-usd', String(budgetUsd),
    ...(model ? ['--model', model] : []),
    '--tools', ...TOOLS,
    '--allowedTools', ...allowList({ kind, pr, baseRef }),
    '--disallowedTools', ...denyList({ kind, denyRead }),
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

// What Claude Code itself needs (login, locale, temp dir). No GH_TOKEN, SSH_AUTH_SOCK, cloud keys or IW_* flags.
const ENV_KEEP = new Set(['PATH', 'HOME', 'USER', 'LOGNAME', 'SHELL', 'LANG', 'TERM', 'TMPDIR', 'TZ', 'CLAUDE_CONFIG_DIR', 'ANTHROPIC_API_KEY', 'ANTHROPIC_BASE_URL']);

/** The session's environment: an allow-list, whatever the caller's shell had */
export function childEnv(env) {
  const out = {};
  for (const [k, v] of Object.entries(env)) if (ENV_KEEP.has(k) || /^LC_[A-Z]+$/.test(k)) out[k] = v;
  out.IWATCH_SESSION = '1';
  return out;
}

const killGroup = (pid) => { try { process.kill(-pid, 'SIGKILL'); } catch { /* already gone */ } };

export function runSession({ spawn = spawnSync, cwd, prompt, args, env, timeoutMs = TIMEOUT_MS, kill = killGroup }) {
  // detached: claude leads its own process group, so a timeout also stops the test runners it started
  const r = spawn('claude', args, { cwd, input: prompt, encoding: 'utf8', timeout: timeoutMs, killSignal: 'SIGKILL', detached: true, maxBuffer: 256 * 1024 * 1024, env: childEnv(env), stdio: ['pipe', 'pipe', 'pipe'] });
  const timedOut = r.error?.code === 'ETIMEDOUT' || r.signal === 'SIGTERM' || r.signal === 'SIGKILL';
  const overflow = r.error?.code === 'ENOBUFS';
  // always: a test runner left in the background must not keep running while the runner pushes
  if (r.pid) kill(r.pid);
  const parsed = parseStream(r.stdout);
  return { ...parsed, code: r.status, timedOut, overflow, stderr: String(r.stderr || '').slice(-2000), ok: !timedOut && !overflow && r.status === 0 && !parsed.isError };
}
