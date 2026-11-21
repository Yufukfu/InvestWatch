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
 * A push is allowed only to `origin` and only for the current branch (ADR 0207). Push options are an
 * allow-list (`-u`, `-v`, `-q`, `-n`, `--set-upstream`, `--no-verify`, `--atomic`, `--dry-run`, `--progress`,
 * `-o <value>`): force (also in a cluster such as `-uf`), `--delete`, `:ref`, `--prune`, `--tags`, abbreviated
 * long options (`--del`, `--rece`), another remote or URL, `--repo`/`--receive-pack`/`--exec`, glob and unreadable
 * (quoted or expanded) refspecs, a destination other than the current branch, a push from a detached HEAD, with
 * `-C`/`--git-dir`/`--work-tree`, or chained after `checkout`/`switch`, are all denied.
 * None of the following takes an escape (IW_ALLOW_GIT=1 does nothing for them, even as a trailing comment):
 *  - every push check above,
 *  - rewiring a remote (`git remote add|set-url|rename|remove`, `git config remote.*|url.*|branch.*.remote|
 *    core.sshCommand`, `git -c` / `--config-env` with the same keys), and any quoted or expanded git subcommand
 *    or `-c` value (a remote could hide in it),
 *  - `gh api` that writes (any method but GET, `-f`/`-F`/`--input` without `-X GET`, GraphQL) or merges or
 *    approves, `gh pr review` with an approve flag in any spelling, and `gh pr create` for another repository
 *    (`--repo`, `-R`, `--head owner:branch`, `GH_REPO=`).
 * Commands are split on `; | && || ( ) \`` and newlines, `git` and `gh` are found by path, and a line
 * continuation joins the command, so `(git push ...)` and `/usr/bin/git push ...` are seen.
 *
 * Escapes: put IW_ALLOW_GIT=1 (destructive git), IW_SKIP_SPEC=1 (spec rule) or IW_CONTRACT_CHANGE=1
 * (contract freeze; only with the whole team's agreement and a version bump) in the command.
 * The escapes are plain text an agent can write itself: this guard catches mistakes, it is not a
 * security boundary. Their use should be reported to the human.
 * Limits: quoted strings and heredocs are stripped before matching; `git commit -a` is checked
 * against `git diff HEAD`; `git commit <paths>` stages those paths and is not seen. The hook reads the
 * command text only: `bash -c '...'`, `python -c`, a script file, environment variables such as
 * GIT_SSH_COMMAND, or editing `.git/config` with a file tool all get past it. What actually limits a push
 * is the narrowed rule `Bash(git push origin:*)` in .claude/settings.json (any other push still asks)
 * plus these checks; merges and `gh pr ready|review` stay gated by `permissions.ask`.
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

// Command separators, subshell and substitution brackets, and backticks: each side is its own command.
const SPLIT = /&&|\|\||[;|\n()`]/;
// A token the guard cannot read after quotes were stripped: quoted, expanded or escaped.
const UNREADABLE = /["'`$\\]/;
const IS_GIT = /(?:^|\/)git$/;
const IS_GH = /(?:^|\/)gh$/;

function parseGit(segment) {
  const tokens = segment.split(/\s+/);
  const at = tokens.findIndex((t) => IS_GIT.test(t));
  if (at === -1) return null;
  let i = at + 1;
  const config = [];
  const global = [];
  let unreadable = false;
  while (i < tokens.length && tokens[i].startsWith('-')) {
    const t = tokens[i];
    global.push(t);
    if ((t === '-c' || t === '--config-env') && i + 1 < tokens.length) {
      config.push(tokens[i + 1]);
      if (UNREADABLE.test(tokens[i + 1])) unreadable = true;
    } else if (t.startsWith('--config-env=')) {
      config.push(t.slice('--config-env='.length));
    }
    i += ['-c', '-C', '--git-dir', '--work-tree', '--config-env'].includes(t) ? 2 : 1;
  }
  if (i >= tokens.length) return null;
  if (UNREADABLE.test(tokens[i])) unreadable = true;
  return { sub: tokens[i], args: tokens.slice(i + 1), config, global, unreadable };
}

// Settings that change where a push goes or how it connects. Never escapable (see redirectReason).
const REDIRECT_KEY = /^(?:remote\.|url\.|core\.sshcommand|core\.gitproxy|branch\.[^\s=]*\.(?:push)?remote)/i;
const REMOTE_WRITE = new Set(['add', 'set-url', 'rename', 'remove', 'rm', 'set-branches']);
const CONFIG_READ = new Set(['--get', '--get-all', '--get-regexp', '--get-urlmatch', '--list', '-l']);
// `gh api` payloads that merge or approve a pull request, in REST or GraphQL spelling.
const GH_MERGE_OR_APPROVE = /\/merge\b|mergePullRequest|enablePullRequestAutoMerge|approvePullRequest|event(?:=|\s*:\s*|\s+)["']?APPROVE/i;

/**
 * Checks that decide whether work can leave the repository or reach `main` without a human.
 * IW_ALLOW_GIT=1 does NOT lift them: an escape is plain text an agent can write itself, and a
 * prompt-injected agent would write it. Ask the human to run the command instead.
 */
function redirectReason({ sub, args, config, global, unreadable }) {
  if (config.some((c) => REDIRECT_KEY.test(c))) return 'inline git config that redirects a remote';
  if (unreadable) return 'git subcommand or -c value the guard cannot read (quoted or expanded); a remote could be hidden in it';
  const flags = args.filter((a) => a.startsWith('-'));
  const positional = args.filter((a) => !a.startsWith('-'));
  if (sub === 'remote' && REMOTE_WRITE.has(positional[0])) {
    return `git remote ${positional[0]} (changes where pushes go)`;
  }
  if (sub === 'config' && !flags.some((f) => CONFIG_READ.has(f)) && positional[0] !== undefined
    && (REDIRECT_KEY.test(positional[0]) || UNREADABLE.test(positional[0]))) {
    return 'git config of a remote, a URL rewrite or an ssh command (changes where pushes go)';
  }
  if (sub === 'push') {
    if (global.some((g) => ['-C', '--git-dir', '--work-tree'].includes(g) || /^--(?:git-dir|work-tree)=/.test(g))) {
      return 'git push with -C, --git-dir or --work-tree (the current branch would be read from the wrong directory)';
    }
    const { flags: pushFlags, positional: pushPositional } = splitPushArgs(args);
    if (pushFlags.some((f) => /^--(?:repo|receive-pack|exec)(?:=|$)/.test(f))) return 'push option that redirects the target';
    if (pushPositional[0] !== undefined && pushPositional[0] !== 'origin') return 'push to a remote other than origin';
  }
  return null;
}

// `gh api` payloads that merge or approve a pull request, in REST or GraphQL spelling.
function ghApiReason(rest, command) {
  if (GH_MERGE_OR_APPROVE.test(command)) return 'gh api call that merges or approves a pull request (a human does that)';
  const after = rest.slice(rest.indexOf('api') + 1);
  let method = null;
  let body = false;
  for (let k = 0; k < after.length; k++) {
    const a = after[k];
    if (a === '-X' || a === '--method') method = after[++k] || '';
    else if (/^-X./.test(a)) method = a.slice(2);
    else if (a.startsWith('--method=')) method = a.slice('--method='.length);
    else if (/^(?:-[fF].*|--(?:field|raw-field|input)(?:=.*)?)$/.test(a)) body = true;
  }
  const effective = String(method || (body ? 'POST' : 'GET')).toUpperCase();
  if (effective !== 'GET' || after.includes('graphql')) {
    return 'gh api call that writes or runs GraphQL (it can reach main without a PR); use gh pr or gh issue, or ask the human';
  }
  return null;
}

function ghReason(command, deps) {
  for (const segment of stripQuoted(command).split(SPLIT)) {
    const t = segment.trim().split(/\s+/);
    const at = t.findIndex((x) => IS_GH.test(x));
    if (at === -1) continue;
    const env = t.slice(0, at);
    const rest = t.slice(at + 1);
    const first = rest.find((x) => x === 'api' || x === 'pr');
    if (first === 'api') {
      const why = ghApiReason(rest, command);
      if (why) return why;
    }
    if (first !== 'pr') continue;
    const sub2 = rest[rest.indexOf('pr') + 1];
    if (sub2 === 'review' && rest.some((a) => /^--approve(?:=.*)?$/.test(a) || /^-[a-zA-Z]*a[a-zA-Z]*$/.test(a))) {
      return 'approving a pull request (a human does that)';
    }
    if (sub2 === 'create') {
      if (env.some((e) => e.startsWith('GH_REPO='))) return 'gh pr create with GH_REPO set (it can target another repository)';
      const ours = deps.originRepo();
      for (let k = 0; k < rest.length; k++) {
        const a = rest[k];
        let repo = null;
        let head = null;
        if (a === '--repo' || a === '-R') repo = rest[k + 1];
        else if (a.startsWith('--repo=')) repo = a.slice('--repo='.length);
        else if (/^-R./.test(a)) repo = a.slice(2);
        else if (a === '--head' || a === '-H') head = rest[k + 1];
        else if (a.startsWith('--head=')) head = a.slice('--head='.length);
        else if (/^-H./.test(a)) head = a.slice(2);
        if (repo !== null && (!ours || String(repo).toLowerCase() !== ours.toLowerCase())) {
          return 'gh pr create for a repository other than this repository';
        }
        if (head !== null && String(head).includes(':')) {
          return 'gh pr create from a branch of a repository other than this repository';
        }
      }
    }
  }
  return null;
}

// A short-flag cluster with f (`-f`, `-uf`, `-fu`) or any --force* option.
const isForce = (a) => (/^-[a-zA-Z]*f/.test(a) && !a.startsWith('--')) || a.startsWith('--force');

// Push flags the guard accepts. Everything else is denied, so an abbreviation of a dangerous long
// option (`--del`, `--rece`, `--mir`) cannot slip past an exact-match list. `-o <value>` takes a value.
const PUSH_FLAGS = new Set(['-u', '--set-upstream', '--no-verify', '-v', '--verbose', '-q', '--quiet', '--atomic', '--dry-run', '-n', '--progress']);
const knownPushFlag = (f) => PUSH_FLAGS.has(f) || /^--push-option=/.test(f) || /^-[uvqn]+$/.test(f);

function splitPushArgs(args) {
  const flags = [];
  const positional = [];
  for (let k = 0; k < args.length; k++) {
    const a = args[k];
    if (a === '-o' || a === '--push-option') k++;
    else if (a.startsWith('-')) flags.push(a);
    else positional.push(a);
  }
  return { flags, positional };
}

// The branch a refspec writes to: `HEAD` means the current branch, `refs/heads/` is stripped,
// `src:dst` uses dst.
function pushTarget(refspec, branch) {
  const spec = refspec.replace(/^\+/, '');
  const dst = spec.includes(':') ? spec.split(':').pop() : spec;
  return dst === 'HEAD' ? branch : dst.replace(/^refs\/heads\//, '');
}

// A push may update the current branch and nothing else: the remote is checked in redirectReason,
// the destination here. Quoted or expanded refspecs are denied because the guard cannot read them.
function checkPush(args, branch) {
  const { flags, positional } = splitPushArgs(args);
  if (flags.some(isForce) || positional.some((a) => a.startsWith('+'))) return 'force push';
  if (flags.includes('--all') || flags.includes('--mirror')) return 'push of every branch (includes main)';
  if (flags.includes('--delete') || flags.includes('-d')) return 'deleting a remote branch';
  if (flags.includes('--prune')) return 'push --prune (deletes remote branches)';
  const unknown = flags.find((f) => !knownPushFlag(f));
  if (unknown) return `push option the guard does not recognise (${unknown}); abbreviations, --tags and unknown options are denied`;
  const refspecs = positional.slice(1);
  for (const raw of refspecs) {
    const spec = raw.replace(/^\+/, '');
    if (spec.startsWith(':')) return 'deleting a remote ref';
    if (spec.includes('*')) return 'glob refspec (cannot tell which branches it updates)';
    if (!branch || branch === 'HEAD') return 'push from a detached HEAD (check out your branch first)';
    const dst = pushTarget(raw, branch);
    if (PROTECTED.includes(dst)) return 'push to main';
    if (!/^[\w./-]+$/.test(dst)) return 'refspec the guard cannot read (quoted or expanded); write the branch name plainly';
    if (dst !== branch) return `push to a branch other than the current branch (${dst})`;
  }
  if (refspecs.length === 0 && PROTECTED.includes(branch)) return `push while on ${branch}`;
  return null;
}

function destructiveReason({ sub, args }, branch, headIsPushed) {
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
  const NO_ESCAPE = 'No escape for this: ask the human to run it themselves.';
  command = command.replace(/\\\r?\n/g, ' '); // a line continuation joins the command
  const viaGh = ghReason(command, deps);
  if (viaGh) return `Blocked: ${viaGh}. ${NO_ESCAPE}`;
  const gits = stripQuoted(command)
    .split(SPLIT)
    .map((s) => parseGit(s.trim()))
    .filter(Boolean);
  if (gits.length === 0) return null;

  // Where work can go and what a push may touch: no escape, whatever the command text says.
  for (const [at, git] of gits.entries()) {
    let why = redirectReason(git);
    if (!why && git.sub === 'push') {
      why = gits.slice(0, at).some((g) => g.sub === 'checkout' || g.sub === 'switch')
        ? 'git push chained after checkout or switch (the current branch is read before the chain runs)'
        : checkPush(git.args, deps.branch());
    }
    if (why) return `Blocked: ${why}. ${NO_ESCAPE}`;
  }

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
    // symbolic-ref also works on a branch without commits, and fails (null) on a detached HEAD.
    branch: () => { try { return git(cwd, ['symbolic-ref', '--short', '-q', 'HEAD']).trim() || null; } catch { return null; } },
    headIsPushed: () => { try { return git(cwd, ['branch', '-r', '--contains', 'HEAD']).trim() !== ''; } catch { return false; } },
    // "owner/name" of origin, so `gh pr create --repo` can be limited to this repository.
    originRepo: () => {
      try {
        const m = git(cwd, ['remote', 'get-url', 'origin']).trim().match(/github\.com[:/]([^/\s]+\/[^/\s]+?)(?:\.git)?$/i);
        return m ? m[1] : null;
      } catch { return null; }
    },
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
