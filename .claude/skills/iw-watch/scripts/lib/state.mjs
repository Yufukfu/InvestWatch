// Seen-state and the run lock. Lives outside the repository (XDG state dir), holds no tokens.
// state.json: { version: 1, prs: { "<n>": { handled, pending, reviewedSha, ciFailedSha, capNotifiedSha, sessions } } }
// Review activity is tracked by event id, not time: GitHub dates a pending review's comments when they were
// drafted, not when the review was submitted, so a time cursor can skip them. `scan` records the event keys of
// each address-review item under `pending`; `ack` moves them to `handled`.
import realFs from 'node:fs';
import path from 'node:path';
import { randomUUID, createHash } from 'node:crypto';

export const STALE_LOCK_MS = 30 * 60 * 1000;
export const HANDLED_MAX = 2000;
const EMPTY = () => ({ version: 1, prs: {} });
const KINDS = { 'address-review': 'handled', 'ci-failed': 'ciFailedSha', review: 'reviewedSha', 'cap-reached': 'capNotifiedSha', conflict: 'conflictSha' };

/** Short stable digest of a set of event keys, used as the cursor of an address-review item */
export const digest = (keys) => createHash('sha256').update([...keys].sort().join('\n')).digest('hex').slice(0, 16);

export function stateDir({ env, home, repo }) {
  if (!/^[A-Za-z0-9._-]+\/[A-Za-z0-9._-]+$/.test(repo) || repo.split('/').some((p) => p === '..' || p === '.')) {
    throw new Error(`not a repository name: ${JSON.stringify(repo)}`);
  }
  const base = env.XDG_STATE_HOME || path.join(home, '.local', 'state');
  return path.join(base, 'iw-watch', repo.replace('/', '__'));
}

export function loadState(dir, { fs = realFs, log = (m) => process.stderr.write(`${m}\n`), now = () => new Date() } = {}) {
  const file = path.join(dir, 'state.json');
  let text;
  try {
    text = fs.readFileSync(file, 'utf8');
  } catch (e) {
    if (e.code === 'ENOENT') return EMPTY();
    throw e;
  }
  try {
    const s = JSON.parse(text);
    if (s && s.version === 1 && s.prs && typeof s.prs === 'object') return s;
  } catch { /* falls through to the backup below */ }
  const backup = `${file}.corrupt-${now().toISOString().replace(/[:.]/g, '-')}`;
  fs.renameSync(file, backup);
  log(`iw-watch: state file was corrupt, moved to ${backup}; starting empty`);
  return EMPTY();
}

/** Write to a temp file and rename it over the old one, so a killed write never leaves half a file */
export function saveState(dir, state, { fs = realFs } = {}) {
  fs.mkdirSync(dir, { recursive: true });
  const file = path.join(dir, 'state.json');
  const tmp = `${file}.tmp-${process.pid}`;
  try {
    fs.writeFileSync(tmp, `${JSON.stringify(state, null, 2)}\n`, { mode: 0o600 });
    fs.renameSync(tmp, file);
  } catch (e) {
    try { realFs.rmSync(tmp, { force: true }); } catch { /* best effort */ }
    throw e;
  }
}

/** Item ids are `<pr>.<kind>.<cursor>`: the cursor is an ISO time (comments, checks) or a head sha */
export function itemId({ kind, pr, cursor }) {
  return `${pr}.${kind}.${cursor}`;
}

export function parseItemId(id) {
  const m = /^(\d+)\.([a-z-]+)\.([A-Za-z0-9:.-]+)$/.exec(String(id));
  if (!m || !KINDS[m[2]]) throw new Error(`not an item id: ${JSON.stringify(id)}`);
  return { pr: Number(m[1]), kind: m[2], cursor: m[3] };
}

const entry = (state, pr) => (state.prs[pr] ??= {});

export function ack(state, id) {
  const { pr, kind, cursor } = parseItemId(id);
  const e = entry(state, pr);
  if (kind === 'address-review') {
    const keys = e.pending?.[id];
    if (!keys) throw new Error(`unknown item id ${id}: not pending (run scan first, or it was already acknowledged)`);
    e.handled = [...new Set([...(e.handled || []), ...keys])].slice(-HANDLED_MAX);
    delete e.pending[id];
    if (!Object.keys(e.pending).length) delete e.pending;
  } else if (kind === 'review' && e.pending?.[id]) {
    // a review round started by my /iw answers: the answers are handled, the head is reviewed
    e.handled = [...new Set([...(e.handled || []), ...e.pending[id]])].slice(-HANDLED_MAX);
    delete e.pending[id];
    if (!Object.keys(e.pending).length) delete e.pending;
    e.reviewedSha = cursor.split('-')[0];
  } else {
    e[KINDS[kind]] = cursor;
  }
  return state;
}

/** Replace the pending address-review items of a PR with the ones the latest scan produced */
export function setPending(state, pr, pending) {
  const e = entry(state, pr);
  if (Object.keys(pending).length) e.pending = pending;
  else delete e.pending;
  return state;
}

export const isHandled = (e, key) => Boolean(e?.handled?.includes(key));

export function recordSession(state, pr) {
  const e = entry(state, pr);
  e.sessions = (e.sessions || 0) + 1;
  return state;
}

export function dropClosed(state, openNumbers) {
  for (const k of Object.keys(state.prs)) if (!openNumbers.has(Number(k))) delete state.prs[k];
  return state;
}

const readOwner = (fs, lock) => {
  try { return JSON.parse(fs.readFileSync(path.join(lock, 'owner.json'), 'utf8')); } catch { return {}; }
};

/**
 * mkdir is atomic: whoever creates the directory holds the lock. Returns a handle, or null if held.
 * A stale lock (older than 30 minutes, see refreshLock) is renamed aside, which only one runner can do;
 * if the moved lock turns out not to be the one judged stale, it is put back and this runner gives up.
 */
export function acquireLock(dir, { fs = realFs, now = () => Date.now() } = {}) {
  fs.mkdirSync(dir, { recursive: true });
  const lock = path.join(dir, 'lock');
  const token = randomUUID();
  for (let attempt = 0; attempt < 3; attempt += 1) {
    try {
      fs.mkdirSync(lock);
      fs.writeFileSync(path.join(lock, 'owner.json'), JSON.stringify({ pid: process.pid, at: now(), token }));
      return { lock, fs, token };
    } catch (e) {
      if (e.code !== 'EEXIST') throw e;
    }
    const owner = readOwner(fs, lock);
    let { at } = owner;
    if (!Number.isFinite(at)) {
      try { at = fs.statSync(lock).mtimeMs; } catch { continue; } // vanished meanwhile: try again
    }
    if (!(now() - at > STALE_LOCK_MS)) return null;
    const aside = `${lock}.stale-${token}`;
    try { fs.renameSync(lock, aside); } catch { continue; }
    if (readOwner(fs, aside).token !== owner.token) {
      try { fs.renameSync(aside, lock); } catch { /* someone holds it now */ }
      return null;
    }
    fs.rmSync(aside, { recursive: true, force: true });
  }
  return null;
}

/** Only the holder releases: a runner whose lock was taken over leaves the new owner alone */
export function releaseLock(handle) {
  if (handle && readOwner(handle.fs, handle.lock).token === handle.token) {
    handle.fs.rmSync(handle.lock, { recursive: true, force: true });
  }
}

/** Heartbeat between items, so a long run is not judged stale */
export function refreshLock(handle, { now = () => Date.now() } = {}) {
  if (handle && readOwner(handle.fs, handle.lock).token === handle.token) {
    handle.fs.writeFileSync(path.join(handle.lock, 'owner.json'), JSON.stringify({ pid: process.pid, at: now(), token: handle.token }));
  }
}
