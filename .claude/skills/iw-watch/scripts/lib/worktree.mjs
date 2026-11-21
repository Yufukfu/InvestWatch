// One disposable clone per handled item, next to the other worktrees: ../InvestWatch-worktrees/watch-pr-<n>.
// A clone, not a `git worktree`: the PR branch is usually checked out in the author's own worktree, and git
// refuses a second worktree of it. The clone borrows objects from the main clone (--reference, then
// --dissociate), has the real `origin` URL, and carries the branch's own .claude/ (settings and git-guard).
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
  const own = item.kind === 'address-review' || item.kind === 'ci-failed';
  git(['clone', '--quiet', '--reference', mainRoot, '--dissociate', '--no-tags', '--branch', own ? item.headRef : item.baseRef, '--', url, dir]);
  if (own) {
    git(['-C', dir, 'fetch', '--quiet', 'origin', `+refs/heads/${item.baseRef}:refs/remotes/origin/${item.baseRef}`]);
  } else {
    // someone else's PR: its head, detached, so nothing here can push to their branch
    git(['-C', dir, 'fetch', '--quiet', 'origin', `refs/pull/${Number(item.pr)}/head`]);
    git(['-C', dir, '-c', 'advice.detachedHead=false', 'checkout', '--quiet', '--detach', 'FETCH_HEAD']);
  }
  return { dir, head: git(['-C', dir, 'rev-parse', 'HEAD']) };
}

/** Commits on the clone's branch that origin does not have */
export function unpushed({ git = realGit, dir, headRef }) {
  try {
    git(['-C', dir, 'fetch', '--quiet', 'origin', `+refs/heads/${headRef}:refs/remotes/origin/${headRef}`]);
  } catch { /* offline: compare with what we have */ }
  return Number(git(['-C', dir, 'rev-list', '--count', `refs/remotes/origin/${headRef}..HEAD`]));
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
