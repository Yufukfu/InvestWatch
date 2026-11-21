#!/usr/bin/env node
/**
 * PreToolUse hook (matcher: Bash). Deterministic, no LLM, no network.
 *
 * Denies:
 *  - force push, push to main, `git reset --hard`, `git clean -f`, whole-tree checkout/restore,
 *    amending a commit that is already on a remote.
 *  - `git commit` whose staged diff (a) includes a .env file (secrets stay out of git),
 *    (b) adds a console.log call to non-test JS/TS code (the jury checks for it),
 *    (c) touches service code while no OpenSpec change is active (spec first),
 *    (d) changes contracts/schemas, contracts/mocks or contracts/openapi.yaml at or after the Sat 14:30 freeze.
 *
 *  - `git add` chained in front of `git commit` in one command (the staged diff is not visible yet).
 *
 * Escapes: put IW_ALLOW_GIT=1 (destructive git), IW_SKIP_SPEC=1 (spec rule) or IW_CONTRACT_CHANGE=1
 * (contract freeze; only with the whole team's agreement and a version bump) in the command.
 * The escapes are plain text an agent can write itself: this guard catches mistakes, it is not a
 * security boundary. Their use should be reported to the human.
 * Limits: quoted strings and heredocs are stripped before matching; `git commit -a` is checked
 * against `git diff HEAD`; `git commit <paths>` stages those paths and is not seen. A push of a feature
 * branch is allowed (ADR 0207); merges stay gated by `permissions.ask` in .claude/settings.json.
 */
'use strict';

const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

const PROTECTED = ['main'];
// Contracts v1 freeze (CLAUDE.md hard rule), Sat 14:30 Europe/Warsaw (CET, +01:00).
const CONTRACT_FREEZE_AT = new Date('2026-11-21T14:30:00+01:00');
// The frozen contract files; the validator and its pins under contracts/ are tooling.
const FROZEN_CONTRACT = /^contracts\/(?:schemas\/|mocks\/|openapi\.yaml$)/;
const SERVICE_DIRS = ['scraper', 'analytics', 'web', 'api', 'contracts'];
const CODE_FILE = /\.(?:[cm]?[jt]sx?)$/;
const TEST_FILE = /(?:\.test\.|\.spec\.|(?:^|\/)(?:tests?|__tests__)\/)/;
const ENV_FILE = /(?:^|\/)\.env(?:\.[\w-]+)?$/;
const ENV_EXAMPLE = /\.env\.(?:example|sample|template)$/;

function stripQuoted(command) {
  return String(command)
    .replace(/<<-?\s*(['"]?)(\w+)\1[\s\S]*?\n\s*\2\b/g, ' ')
    .replace(/'[^']*'/g, "''")
    .replace(/"(?:\\.|[^"\\])*"/g, '""');
}

function parseGit(segment) {
  const tokens = segment.split(/\s+/);
  const at = tokens.indexOf('git');
  if (at === -1) return null;
  let i = at + 1;
  while (i < tokens.length && tokens[i].startsWith('-')) {
    i += ['-c', '-C', '--git-dir', '--work-tree'].includes(tokens[i]) ? 2 : 1;
  }
  return i < tokens.length ? { sub: tokens[i], args: tokens.slice(i + 1) } : null;
}

const isForce = (a) => a === '-f' || a === '--force' || a.startsWith('--force-with-lease') || a === '--force-if-includes';

// The branch a refspec writes to: `HEAD` means the current branch, `refs/heads/` is stripped,
// `src:dst` uses dst.
function pushTarget(refspec, branch) {
  const spec = refspec.replace(/^\+/, '');
  const dst = spec.includes(':') ? spec.split(':').pop() : spec;
  return dst === 'HEAD' ? branch : dst.replace(/^refs\/heads\//, '');
}

function checkPush(args, branch) {
  const flags = args.filter((a) => a.startsWith('-'));
  const positional = args.filter((a) => !a.startsWith('-'));
  if (flags.some(isForce) || positional.some((a) => a.startsWith('+'))) return 'force push';
  if (flags.includes('--all') || flags.includes('--mirror')) return 'push of every branch (includes main)';
  const refspecs = positional.slice(1);
  if (refspecs.some((r) => PROTECTED.includes(pushTarget(r, branch)))) return 'push to main';
  if (refspecs.length === 0 && PROTECTED.includes(branch)) return `push while on ${branch}`;
  return null;
}

function destructiveReason({ sub, args }, branch, headIsPushed) {
  if (sub === 'push') return checkPush(args, branch);
  if (sub === 'reset' && args.includes('--hard')) return 'git reset --hard';
  if (sub === 'clean' && args.some((a) => a === '--force' || /^-[a-zA-Z]*f/.test(a))) return 'git clean -f';
  if (sub === 'branch' && args.includes('-D') && args.some((a) => PROTECTED.includes(a))) return 'deleting main';
  const wholeTree = args.some((a) => ['.', ':/', './'].includes(a));
  if ((sub === 'checkout' || sub === 'restore') && wholeTree && !(sub === 'restore' && args.includes('--staged'))) {
    return `git ${sub} of the whole tree (discards all uncommitted changes)`;
  }
  if (sub === 'commit' && args.includes('--amend') && headIsPushed()) {
    return 'amending a pushed commit (add a follow-up commit instead)';
  }
  return null;
}

/** staged: [{ file, added: string[] }]; activeChanges: names of non-archived OpenSpec changes. */
function commitReason(staged, activeChanges, skipSpec, contractsFrozen = false) {
  const env = staged.find((s) => ENV_FILE.test(s.file) && !ENV_EXAMPLE.test(s.file));
  if (env) return `${env.file} is staged. Secrets live in untracked .env files; commit .env.example instead.`;

  const logged = staged.find(
    (s) => CODE_FILE.test(s.file) && !TEST_FILE.test(s.file) && s.added.some((l) => /\bconsole\.log\s*\(/.test(l)),
  );
  if (logged) return `console.log added in ${logged.file}. Use the service logger (JSON on stdout).`;

  const contract = contractsFrozen && staged.find((s) => FROZEN_CONTRACT.test(s.file));
  if (contract) {
    return `${contract.file} is staged but contracts are frozen (since Sat 14:30). A change needs the whole team and a version bump (escape: IW_CONTRACT_CHANGE=1).`;
  }

  const touchesService = staged.some((s) => SERVICE_DIRS.includes(s.file.split('/')[0]) && !/\.md$/i.test(s.file));
  const touchesSpec = staged.some((s) => s.file.startsWith('openspec/changes/') && !s.file.startsWith('openspec/changes/archive/'));
  if (touchesService && !touchesSpec && activeChanges.length === 0 && !skipSpec) {
    return 'Service code is staged but no OpenSpec change is active. Run /openspec-propose first (escape for trivial fixes: IW_SKIP_SPEC=1).';
  }
  return null;
}

function evaluate(command, deps) {
  if (typeof command !== 'string' || !command) return null;
  const gits = stripQuoted(command)
    .split(/&&|\|\||[;|\n]/)
    .map((s) => parseGit(s.trim()))
    .filter(Boolean);
  if (gits.length === 0) return null;

  if (!/IW_ALLOW_GIT=1/.test(command)) {
    for (const git of gits) {
      const why = destructiveReason(git, deps.branch(), deps.headIsPushed);
      if (why) return `Blocked: ${why}. Needs an explicit user decision. Escape: IW_ALLOW_GIT=1.`;
    }
  }
  const commitAt = gits.findIndex((g) => g.sub === 'commit');
  if (commitAt === -1) return null;
  if (gits.slice(0, commitAt).some((g) => g.sub === 'add')) {
    return 'Run `git add` in a separate call before `git commit`: the guard reads the staged diff when the command starts, so an add chained in front of the commit is not checked.';
  }
  const commit = gits[commitAt];
  const all = commit.args.some((a) => /^-[a-zA-Z]*a/.test(a) && !a.startsWith('--')) || commit.args.includes('--all');
  const frozen = deps.now() >= CONTRACT_FREEZE_AT && !/IW_CONTRACT_CHANGE=1/.test(stripQuoted(command));
  return commitReason(deps.staged(all), deps.activeChanges(), /IW_SKIP_SPEC=1/.test(command), frozen);
}

function git(cwd, args) {
  return execFileSync('git', args, { cwd, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'], maxBuffer: 16 * 1024 * 1024 });
}

function defaultDeps(cwd) {
  return {
    now: () => new Date(),
    branch: () => { try { return git(cwd, ['rev-parse', '--abbrev-ref', 'HEAD']).trim(); } catch { return null; } },
    headIsPushed: () => { try { return git(cwd, ['branch', '-r', '--contains', 'HEAD']).trim() !== ''; } catch { return false; } },
    staged: (all) => {
      try {
        const base = all ? 'HEAD' : '--cached';
        const out = [];
        for (const line of git(cwd, ['diff', base, '-U0', '--no-color', '--no-renames']).split('\n')) {
          if (line.startsWith('+++ ')) out.push({ file: line.slice(4).replace(/^b\//, ''), added: [] });
          else if (line.startsWith('+') && out.length) out[out.length - 1].added.push(line.slice(1));
        }
        const names = git(cwd, ['diff', base, '--name-only', '--no-renames']).split('\n').filter(Boolean);
        return names.map((file) => out.find((o) => o.file === file) || { file, added: [] });
      } catch { return []; }
    },
    activeChanges: () => {
      try {
        const dir = path.join(git(cwd, ['rev-parse', '--show-toplevel']).trim(), 'openspec', 'changes');
        return fs.readdirSync(dir, { withFileTypes: true }).filter((d) => d.isDirectory() && d.name !== 'archive').map((d) => d.name);
      } catch { return []; }
    },
  };
}

if (require.main === module) {
  let data = '';
  process.stdin.setEncoding('utf8');
  process.stdin.on('data', (c) => { data += c; });
  process.stdin.on('end', () => {
    let input = null;
    try { input = JSON.parse(data); } catch { process.exit(0); }
    const cwd = input.cwd || process.cwd();
    const reason = evaluate(input.tool_input && input.tool_input.command, defaultDeps(cwd));
    if (reason) {
      process.stdout.write(JSON.stringify({
        hookSpecificOutput: { hookEventName: 'PreToolUse', permissionDecision: 'deny', permissionDecisionReason: reason },
      }));
    }
    process.exit(0);
  });
}

module.exports = { evaluate, commitReason, destructiveReason, stripQuoted, parseGit };
