// Seen-state and the run lock. Lives outside the repository (XDG state dir), holds no tokens.
// state.json: { version: 1, prs: { "<n>": { seenAt, reviewedSha, capNotifiedSha, sessions } } }
import realFs from 'node:fs';
import path from 'node:path';

export const STALE_LOCK_MS = 30 * 60 * 1000;
const EMPTY = () => ({ version: 1, prs: {} });
const KINDS = { 'address-review': 'seenAt', 'ci-failed': 'seenAt', review: 'reviewedSha', 'cap-reached': 'capNotifiedSha' };

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
  fs.writeFileSync(tmp, `${JSON.stringify(state, null, 2)}\n`);
  try {
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
  const field = KINDS[kind];
  if (field === 'seenAt') {
    if (!e.seenAt || Date.parse(cursor) > Date.parse(e.seenAt)) e.seenAt = cursor;
  } else {
    e[field] = cursor;
  }
  return state;
}

export function recordSession(state, pr) {
  const e = entry(state, pr);
  e.sessions = (e.sessions || 0) + 1;
  return state;
}

export function dropClosed(state, openNumbers) {
  for (const k of Object.keys(state.prs)) if (!openNumbers.has(Number(k))) delete state.prs[k];
  return state;
}

/** mkdir is atomic: whoever creates the directory holds the lock. Returns a handle, or null if held. */
export function acquireLock(dir, { fs = realFs, now = () => Date.now() } = {}) {
  fs.mkdirSync(dir, { recursive: true });
  const lock = path.join(dir, 'lock');
  for (let attempt = 0; attempt < 2; attempt += 1) {
    try {
      fs.mkdirSync(lock);
      fs.writeFileSync(path.join(lock, 'owner.json'), JSON.stringify({ pid: process.pid, at: now() }));
      return { lock, fs };
    } catch (e) {
      if (e.code !== 'EEXIST') throw e;
      let at = 0;
      try { at = JSON.parse(fs.readFileSync(path.join(lock, 'owner.json'), 'utf8')).at; } catch { at = fs.statSync(lock).mtimeMs; }
      if (now() - at <= STALE_LOCK_MS) return null;
      fs.rmSync(lock, { recursive: true, force: true });
    }
  }
  return null;
}

export function releaseLock(handle) {
  if (handle) handle.fs.rmSync(handle.lock, { recursive: true, force: true });
}
