// One disposable clone per handled item, next to the other worktrees: ../InvestWatch-worktrees/watch-pr-<n>.
// A clone, not a `git worktree`: the PR branch is usually checked out in the author's own worktree, and git
// refuses a second worktree of it. The clone borrows objects from the main clone (--reference, then
// --dissociate) and has the real `origin` URL. A fix runs on the PR branch only when the branch leaves
// .claude/, CLAUDE.md, .github/ and .mcp.json as the base has them: those load as settings, hooks and
// instructions, and project hooks run even in an untrusted directory (Adam, PR #48).
import realFs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { safeBranch } from './prompt.mjs';

export class NeedsHuman extends Error {}

export const realGit = (args, opts = {}) => execFileSync('git', args, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], ...opts }).trim();

/** The main clone: the parent of the shared git dir, so a run started inside a worktree finds it too */
export function findMainRoot({ git = realGit, cwd = process.cwd() } = {}) {
  const common = git(['rev-parse', '--path-format=absolute', '--git-common-dir'], { cwd });
  return path.dirname(common);
}

export const clonePath = ({ mainRoot, pr }) => path.join(path.dirname(mainRoot), 'InvestWatch-worktrees', `watch-pr-${Number(pr)}`);

export function prepareClone({ git = realGit, fs = realFs, mainRoot, item }) {
  for (const b of [item.headRef, item.baseRef]) if (!safeBranch(b)) throw new NeedsHuman(`refused branch name ${JSON.stringify(b)}`);
  const dir = clonePath({ mainRoot, pr: item.pr });
  if (fs.existsSync(dir)) throw new NeedsHuman(`${dir} is left from an earlier run; look at it, then remove it to let the watcher retry`);
  fs.mkdirSync(path.dirname(dir), { recursive: true });
  const url = git(['-C', mainRoot, 'remote', 'get-url', 'origin']);
  const own = ['address-review', 'ci-failed', 'conflict'].includes(item.kind);
  // core.commitGraph=false: a stale commit-graph in the reference repo made checkout fail with
  // "unable to parse commit" on the first live run (PR #39); the objects themselves were fine
  try {
    return populate({ git, fs, mainRoot, item, dir, url, own });
  } catch (e) {
    // the directory is ours (it did not exist above): a half-made clone must not block the next run
    fs.rmSync(dir, { recursive: true, force: true });
    throw e;
  }
}

function populate({ git, fs, mainRoot, item, dir, url, own }) {
  git(['-c', 'core.commitGraph=false', 'clone', '--quiet', '--reference', mainRoot, '--dissociate', '--no-tags', '--branch', own ? item.headRef : item.baseRef, '--', url, dir]);
  let head;
  let baseSha;
  if (own) {
    git(['-C', dir, 'fetch', '--quiet', 'origin', `+refs/heads/${item.baseRef}:refs/remotes/origin/${item.baseRef}`]);
    head = git(['-C', dir, 'rev-parse', 'HEAD']);
    // shas, not refs: a sandboxed session can rewrite .git/refs (probed), so the push check diffs against these
    baseSha = git(['-C', dir, 'rev-parse', `refs/remotes/origin/${item.baseRef}`]);
    if (item.headSha && head !== item.headSha) throw new NeedsHuman(`the branch moved since the scan (${head.slice(0, 12)}, scanned ${String(item.headSha).slice(0, 12)}); the next run picks up the new head`);
    const touched = protectedPaths(git(['-C', dir, ...NAMES, `origin/${item.baseRef}...HEAD`]));
    if (touched.length) throw new NeedsHuman(`the branch changes ${touched.slice(0, 3).join(', ')}: settings, hooks or agent instructions; an agent does not run on it, over to you`);
    // a symlink could point the Read tool outside the clone (the sandbox bounds Bash, not Read)
    const links = git(['-C', dir, 'diff', '--raw', '--no-renames', `origin/${item.baseRef}...HEAD`]).split('\n').filter((l) => / 120000 [0-9a-f]+ [0-9a-f]+ [AMT]\t/.test(l));
    if (links.length) throw new NeedsHuman(`the branch adds or changes ${links.length} symlink${links.length > 1 ? 's' : ''}; an agent does not run on it, over to you`);
  } else {
    // Someone else's PR is never checked out: its .claude/ (hooks, settings) and CLAUDE.md would load in the
    // session, and project hooks run even in an untrusted directory. The working tree stays on the base
    // branch; the PR head is a ref to diff and `git show` against.
    git(['-C', dir, 'fetch', '--quiet', 'origin', `+refs/pull/${Number(item.pr)}/head:${prRef(item.pr)}`]);
    head = git(['-C', dir, 'rev-parse', prRef(item.pr)]);
  }
  if (fs.existsSync(path.join(dir, '.iw-watch'))) {
    throw new NeedsHuman(`the branch already contains .iw-watch/ (the watcher's draft folder); refusing to run in ${dir}`);
  }
  fs.mkdirSync(path.join(dir, '.git', 'info'), { recursive: true });
  fs.appendFileSync(path.join(dir, '.git', 'info', 'exclude'), '\n.iw-watch/\n');
  return { dir, head, baseSha };
}

export const prRef = (pr) => `refs/iw/pr-${Number(pr)}`;

// What loads as settings, hooks or agent instructions, or changes CI: never touched by an unattended run
// Case-insensitive: macOS checks `.Claude/` out as `.claude/`. A branch .npmrc would steer the runner's npm ci.
const PROTECTED = /^(\.claude\/|\.github\/|\.mcp\.json$|\.iw-watch\/|\.gitmodules$)|(^|\/)(CLAUDE\.md|CLAUDE\.local\.md|\.npmrc|\.yarnrc(\.yml)?|\.gitattributes)$/i;
// Fed by `git diff --name-only -z --no-renames`: NUL-separated, so a non-ASCII path is not quoted, and a rename
// lists its source too (a rename out of .claude/ is a change to .claude/) (Adam, PR #48)
export const NAMES = ['diff', '--name-only', '-z', '--no-renames'];
export const protectedPaths = (nameOnly) => String(nameOnly || '').split(/[\0\n]/).filter((f) => f && PROTECTED.test(f));

/**
 * Protected paths the agent changed, checked before the runner pushes: they differ from the PR branch AND from
 * the base. A merge brings the base's own .claude/ changes, which differ only from the branch.
 */
export function newCommitPaths({ git = realGit, dir, headSha, baseSha }) {
  const vsBranch = protectedPaths(git(['-C', dir, ...NAMES, headSha, 'HEAD']));
  if (!baseSha) return vsBranch;
  const vsBase = new Set(protectedPaths(git(['-C', dir, ...NAMES, baseSha, 'HEAD'])));
  return vsBranch.filter((f) => vsBase.has(f));
}

/** What the push would carry beyond the PR head: the text diff and messages to scan, and binary files to refuse */
export function pushedContent({ git = realGit, dir, headSha }) {
  const numstat = git(['-C', dir, 'diff', '--numstat', '-z', '--no-renames', headSha, 'HEAD']);
  const binary = numstat.split('\0').filter((l) => /^-\t-\t/.test(l)).map((l) => l.slice(4));
  const text = git(['-C', dir, 'diff', '--no-renames', '--no-ext-diff', '--no-textconv', headSha, 'HEAD'], { maxBuffer: 16 * 1024 * 1024 });
  const messages = git(['-C', dir, 'log', '--format=%B', `${headSha}..HEAD`]);
  return { binary, text: `${text}\n${messages}` };
}

/** The runner pushes, not the session: never force, only to the PR's own branch name */
export function pushBranch({ git = realGit, dir, headRef }) {
  if (!safeBranch(headRef)) throw new NeedsHuman(`refused branch name ${JSON.stringify(headRef)}`);
  git(['-C', dir, 'push', '--quiet', 'origin', `HEAD:refs/heads/${headRef}`]);
}

/**
 * The session has no network, so the runner installs the lockfiles first: `npm ci --ignore-scripts` in each
 * top-level package the PR touches. No install scripts run; the session's own environment (no tokens).
 */
export function installDeps({ fs = realFs, run, dir, files, env }) {
  const dirs = [...new Set((files || []).map((f) => f.split('/')[0]).filter((d) => /^[A-Za-z0-9._-]+$/.test(d) && d !== '..'))];
  const out = [];
  for (const d of dirs) {
    const pkg = path.join(dir, d);
    if (!fs.existsSync(path.join(pkg, 'package-lock.json'))) continue;
    try {
      run('npm', ['ci', '--ignore-scripts', '--no-audit', '--no-fund'], { cwd: pkg, env, timeout: 10 * 60 * 1000, stdio: 'ignore' });
      out.push({ dir: d, ok: true });
    } catch (e) {
      out.push({ dir: d, ok: false, error: String(e.message).split('\n')[0] });
    }
  }
  return out;
}

/** Commits on the clone's branch that origin does not have */
export function unpushed({ git = realGit, dir, headRef }) {
  try {
    git(['-C', dir, 'fetch', '--quiet', 'origin', `+refs/heads/${headRef}:refs/remotes/origin/${headRef}`]);
  } catch { /* offline: compare with what we have */ }
  return Number(git(['-C', dir, 'rev-list', '--count', `refs/remotes/origin/${headRef}..HEAD`]));
}

/** .env files in the main clone and the sibling worktrees: a sandboxed command must not read them */
export function findEnvFiles({ fs = realFs, mainRoot }) {
  const roots = [mainRoot];
  const wt = path.join(path.dirname(mainRoot), 'InvestWatch-worktrees');
  try { for (const d of fs.readdirSync(wt)) roots.push(path.join(wt, d)); } catch { /* no worktrees */ }
  const out = [];
  const walk = (dir, depth) => {
    let entries;
    try { entries = fs.readdirSync(dir, { withFileTypes: true }); } catch { return; }
    for (const e of entries) {
      if (e.isFile() && /^\.env(\..+)?$/.test(e.name) && !/\.example$/.test(e.name)) out.push(path.join(dir, e.name));
      else if (e.isDirectory() && depth < 2 && !['node_modules', '.git', '.venv'].includes(e.name)) walk(path.join(dir, e.name), depth + 1);
    }
  };
  for (const r of roots) walk(r, 0);
  return out;
}

const MARKER_LINE = /^(<{7}|>{7}|={7})( |$)/m;

/** Merge origin/<base> into the PR branch; returns the files git could not resolve, or why it refused */
export function startMerge({ git, dir, baseRef }) {
  try {
    git(['-C', dir, 'merge', '--no-ff', '--no-commit', '--no-edit', `origin/${baseRef}`]);
  } catch { /* conflicts: git exits 1 and leaves them in the index */ }
  const files = git(['-C', dir, ...NAMES, '--diff-filter=U']).split('\0').filter(Boolean);
  const bad = protectedPaths(files.join('\0'));
  if (bad.length) {
    try { git(['-C', dir, 'merge', '--abort']); } catch { /* nothing to abort */ }
    return { refused: `the merge with ${baseRef} conflicts in ${bad.slice(0, 3).join(', ')}: settings, hooks or agent instructions, over to you`, files };
  }
  if (!files.length) git(['-C', dir, 'commit', '--quiet', '--no-edit']);
  return { files };
}

/** After the session: every conflict resolved and staged, no markers left; then the runner commits the merge */
export function finishMerge({ fs = realFs, git, dir, files, headRef, baseRef }) {
  const unmerged = git(['-C', dir, ...NAMES, '--diff-filter=U']).split('\0').filter(Boolean);
  if (unmerged.length) return `${unmerged.length} file(s) still have unresolved conflicts: ${unmerged.slice(0, 3).join(', ')}`;
  const marked = (files || []).filter((f) => { try { return MARKER_LINE.test(fs.readFileSync(path.join(dir, f), 'utf8')); } catch { return false; } });
  if (marked.length) return `conflict markers are left in ${marked.slice(0, 3).join(', ')}`;
  if (fs.existsSync(path.join(dir, '.git', 'MERGE_HEAD'))) git(['-C', dir, 'commit', '--quiet', '--no-edit', '-m', `Merge origin/${baseRef} into ${headRef}`]);
  return null;
}

/** What git would run or obey in the clone: config, hooks, attributes. Compared before and after a session. */
export function gitSnapshot({ fs = realFs, dir }) {
  const g = path.join(dir, '.git');
  const read = (p) => { try { return fs.readFileSync(p, 'utf8'); } catch { return null; } };
  let hooks = [];
  try { hooks = fs.readdirSync(path.join(g, 'hooks')).sort().map((h) => [h, read(path.join(g, 'hooks', h))]); } catch { /* none */ }
  return JSON.stringify({ config: read(path.join(g, 'config')), attributes: read(path.join(g, 'info', 'attributes')), hooks });
}

export function removeClone({ fs = realFs, dir }) {
  fs.rmSync(dir, { recursive: true, force: true });
}

/** Copy the agent's outward texts (.iw-watch/*.md) out of the clone before it is removed */
export function collectDrafts({ fs = realFs, dir, to }) {
  fs.mkdirSync(to, { recursive: true, mode: 0o700 });
  const src = path.join(dir, '.iw-watch');
  if (!fs.existsSync(src)) return [];
  const copied = [];
  for (const f of fs.readdirSync(src)) {
    if (!/^[A-Za-z0-9._-]+\.md$/.test(f)) continue;
    const from = path.join(src, f);
    if (!fs.lstatSync(from).isFile()) continue; // no symlinks out of the clone
    fs.copyFileSync(from, path.join(to, f));
    copied.push(f);
  }
  return copied;
}
